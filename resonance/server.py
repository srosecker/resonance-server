"""
Resonance Music Server - Main Server Module

This module contains the main ResonanceServer class that orchestrates
all server components and manages the application lifecycle.
"""

import asyncio
import hashlib
import logging
import signal
import time
import uuid
from pathlib import Path

from resonance.core.artwork import ArtworkManager
from resonance.core.events import Event, PlayerTrackFinishedEvent, event_bus
from resonance.core.library import MusicLibrary
from resonance.core.library_db import LibraryDb
from resonance.core.playlist import PlaylistManager
from resonance.player.registry import PlayerRegistry
from resonance.protocol.discovery import UDPDiscoveryServer
from resonance.protocol.slimproto import SlimprotoServer
from resonance.streaming.seek_coordinator import init_seek_coordinator
from resonance.streaming.server import StreamingServer
from resonance.web.server import WebServer

logger = logging.getLogger(__name__)

# Path for persisting server UUID
SERVER_UUID_FILE = Path("cache/server_uuid")


def get_or_create_server_uuid() -> str:
    """
    Get or create a persistent server UUID.

    The UUID is stored in cache/server_uuid and reused across restarts.
    This matches LMS behavior where each server has a unique identity.

    Format: Full UUID v4 string (36 chars with dashes), e.g. "1a421556-465b-4802-9599-654aa2d6dbd4"
    LMS uses: UUID::Tiny::create_UUID_as_string(UUID_V4())
    """
    SERVER_UUID_FILE.parent.mkdir(parents=True, exist_ok=True)

    if SERVER_UUID_FILE.exists():
        try:
            stored_uuid = SERVER_UUID_FILE.read_text().strip()
            # Accept both old 8-char format and new 36-char UUID v4 format
            # If old format, we'll regenerate a proper UUID
            if stored_uuid and len(stored_uuid) == 36 and stored_uuid.count('-') == 4:
                logger.debug("Using existing server UUID: %s", stored_uuid)
                return stored_uuid
            elif stored_uuid:
                logger.info("Upgrading old 8-char UUID to full UUID v4 format")
        except Exception as e:
            logger.warning("Could not read server UUID: %s", e)

    # Generate new UUID v4 (full 36-char format like LMS)
    # LMS uses: UUID::Tiny::create_UUID_as_string(UUID_V4())
    new_uuid = str(uuid.uuid4())

    try:
        SERVER_UUID_FILE.write_text(new_uuid)
        logger.info("Generated new server UUID: %s", new_uuid)
    except Exception as e:
        logger.warning("Could not save server UUID: %s", e)

    return new_uuid


class ResonanceServer:
    """
    Main Resonance server that coordinates all components.

    The server manages:
    - Slimproto protocol server (port 3483) for player communication
    - Streaming server for audio delivery
    - Player registry for tracking connected players
    - Core music library (SQLite + scanner)
    - Playlist manager for per-player queues
    - Web server for HTTP/JSON-RPC API

    NOTE ON TRACK ADVANCEMENT:
    - We auto-advance the playlist on Slimproto STAT "STMu" (underrun / buffer empty).
    - This matches LMS behavior: only STMu triggers playerStopped(), not STMd.
    - When the user manually starts a new track (e.g. via Web-UI), a late STMu from the
      previous stream can arrive after the manual switch and incorrectly advance to the
      next track. To prevent this, we use stream generation checks and a short
      suppression window immediately after a manual track start.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 3483,
        *,
        web_port: int = 9000,
        music_root: Path | None = None,
        library_db_path: Path | None = None,
    ) -> None:
        """
        Initialize the Resonance server.

        Args:
            host: Host address to bind to.
            port: Slimproto port (default 3483).
            web_port: HTTP/JSON-RPC port (default 9000).
            music_root: Optional root directory for the local music library.
            library_db_path: Optional path to the library SQLite DB file.
        """
        self.host = host
        self.port = port
        self.web_port = web_port

        # Core components
        self.player_registry = PlayerRegistry()

        # Streaming server (handles audio file requests from players)
        self.streaming_server = StreamingServer(
            host=host,
            port=web_port,
            audio_provider=self._resolve_audio_for_player,
        )

        self.slimproto = SlimprotoServer(
            host=host,
            port=port,
            streaming_port=web_port,
            player_registry=self.player_registry,
        )
        # Link back to ResonanceServer for track-finished suppression
        # Note: Use _resonance_server to avoid conflict with SlimprotoServer._server (asyncio server)
        self.slimproto._resonance_server = self

        # Expose StreamingServer on SlimprotoServer so the STAT handler can attach
        # the current stream generation to track-finished events (STMu) and ignore stale events.
        self.slimproto.streaming_server = self.streaming_server

        # Keep DB near the working directory by default; can be overridden.
        default_db_path = Path("resonance-library.sqlite3")
        self.library_db = LibraryDb(db_path=str(library_db_path or default_db_path))

        # Core library (kept independent of any web/UI layer)
        self.music_library = MusicLibrary(db=self.library_db, music_root=music_root)

        # Artwork manager (handles cover art extraction and caching)
        self.artwork_manager = ArtworkManager(cache_dir=Path("cache/artwork"))

        # Playlist manager (one playlist per player)
        self.playlist_manager = PlaylistManager()

        # Web server (HTTP/JSON-RPC on port 9000)
        self.web_server: WebServer | None = None

        # Server state
        self._running = False
        self._shutdown_event: asyncio.Event | None = None

        # Per-player suppression window for STMu-based auto-advance (race protection).
        # Key: player MAC, Value: event-loop time() until which track-finished should be ignored.
        self._suppress_track_finished_until: dict[str, float] = {}

        # SeekCoordinator for latest-wins seek semantics (initialized on start)
        self.seek_coordinator = None

        # Server UUID (persistent across restarts, like LMS)
        self.server_uuid = get_or_create_server_uuid()

        # UDP Discovery server for player discovery on local network
        # NOTE: version="7.999.999" is required for firmware compatibility!
        # SqueezePlay firmware 7.7.3 and earlier has a version comparison bug
        # that rejects servers reporting version 8.0.0 or higher.
        # LMS uses "7.999.999" (RADIO_COMPATIBLE_VERSION) to bypass this.
        self.discovery_server = UDPDiscoveryServer(
            host=host,
            port=port,  # Same port as Slimproto (3483)
            server_name="Resonance",
            http_port=web_port,
            server_uuid=self.server_uuid,
            version="7.999.999",
        )

    async def start(self) -> None:
        """Start all server components."""
        logger.info("Starting Resonance server on %s:%d", self.host, self.port)

        self._running = True
        self._shutdown_event = asyncio.Event()

        # Start core library DB (schema/migrations)
        await self.library_db.open()
        await self.library_db.ensure_schema()

        # Mark the facade initialized (DB-backed operations will be wired in next)
        await self.music_library.initialize()

        # Start Slimproto server
        await self.slimproto.start()

        # Start UDP Discovery server (allows players to find us via broadcast)
        try:
            await self.discovery_server.start()
        except Exception as e:
            # Discovery is optional - don't fail startup if it doesn't work
            logger.warning("UDP Discovery failed to start (players can still connect directly): %s", e)

        # Mark streaming server as ready (no longer binds its own port)
        # Streaming is now handled via FastAPI routes at /stream.mp3
        await self.streaming_server.start()

        # Initialize SeekCoordinator with StreamingServer for generation tracking.
        # This provides latest-wins semantics and safe subprocess termination for seeks.
        self.seek_coordinator = init_seek_coordinator(self.streaming_server)

        # Start Web server (HTTP/JSON-RPC + Streaming)
        self.web_server = WebServer(
            player_registry=self.player_registry,
            music_library=self.music_library,
            playlist_manager=self.playlist_manager,
            streaming_server=self.streaming_server,
            artwork_manager=self.artwork_manager,
            slimproto=self.slimproto,
            server_uuid=self.server_uuid,
        )
        await self.web_server.start(host=self.host, port=self.web_port)

        # Subscribe to track finished events for automatic playlist advancement
        async def _on_track_finished_event(event: Event) -> None:
            if isinstance(event, PlayerTrackFinishedEvent):
                await self._on_track_finished(event)

        await event_bus.subscribe("player.track_finished", _on_track_finished_event)

        logger.info("Resonance server started successfully")
        logger.info("Slimproto: port %d | Web/Streaming: port %d", self.port, self.web_port)

    async def stop(self) -> None:
        """Stop all server components gracefully."""
        if not self._running:
            return

        logger.info("Stopping Resonance server...")
        self._running = False

        # Stop Web server first (clients get 503)
        if self.web_server:
            await self.web_server.stop()

        # Stop UDP Discovery server
        await self.discovery_server.stop()

        # Stop Streaming server (clears queue)
        await self.streaming_server.stop()

        # Stop Slimproto server
        await self.slimproto.stop()

        # Disconnect all players
        await self.player_registry.disconnect_all()

        # Close library DB last, after all components are stopped.
        await self.library_db.close()

        if self._shutdown_event:
            self._shutdown_event.set()

        logger.info("Resonance server stopped")

    async def run(self) -> None:
        """
        Run the server until shutdown is requested.

        This method starts all components and waits for a shutdown signal
        (SIGINT or SIGTERM).
        """
        await self.start()

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()

        def handle_signal() -> None:
            logger.info("Received shutdown signal")
            if self._shutdown_event:
                self._shutdown_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, handle_signal)
            except NotImplementedError:
                # Signal handlers not supported on Windows
                pass

        # Wait for shutdown
        if self._shutdown_event:
            await self._shutdown_event.wait()

        await self.stop()

    @property
    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self._running

    @property
    def connected_players(self) -> int:
        """Get the number of currently connected players."""
        return len(self.player_registry)

    def _resolve_audio_for_player(self, player_mac: str) -> Path | None:
        """
        Callback for StreamingServer to resolve which audio file to serve.

        This looks up the player's playlist and returns the path of the
        current track.

        Args:
            player_mac: MAC address of the requesting player.

        Returns:
            Path to the audio file, or None if no track is queued.
        """
        if player_mac not in self.playlist_manager:
            return None

        playlist = self.playlist_manager.get(player_mac)
        current = playlist.current_track
        if current is None:
            return None

        return Path(current.path)

    async def _on_track_finished(self, event: PlayerTrackFinishedEvent) -> None:
        """Handle track finished event by playing the next track in the playlist."""
        player_id = event.player_id

        # Suppress late STMu from a previous stream right after a manual track start.
        # This prevents: user clicks track A -> server starts A -> late STMu arrives -> server jumps to next.
        now = asyncio.get_running_loop().time()
        suppress_until = self._suppress_track_finished_until.get(player_id)
        if suppress_until is not None and now < suppress_until:
            logger.info(
                "Ignoring track-finished for player %s (suppressed %.3fs remaining)",
                player_id,
                suppress_until - now,
            )
            return

        # Ignore stale track-finished events by stream generation.
        #
        # We attach a per-player stream generation to STMu events (see slimproto STAT handler).
        # When the user manually switches tracks, the streaming server increments generation.
        # A late STMu from the previous stream must NOT advance the playlist to track +1.
        if event.stream_generation is not None:
            current_gen = self.streaming_server.get_stream_generation(player_id)
            if current_gen is not None and current_gen != event.stream_generation:
                logger.info(
                    "Ignoring stale track-finished for player %s (event gen=%s, current gen=%s)",
                    player_id,
                    event.stream_generation,
                    current_gen,
                )
                return

        player = await self.player_registry.get_by_mac(player_id)
        if not player:
            return

        playlist = self.playlist_manager.get(player_id)
        next_track = playlist.next()

        if next_track:
            logger.info("Advancing to next track for player %s: %s", player_id, next_track.title)

            # Queue file in streaming server
            self.streaming_server.queue_file(player_id, Path(next_track.path))

            # Start streaming
            server_ip = self.slimproto.get_advertise_ip_for_player(player)
            await player.start_track(
                next_track,
                server_port=self.web_port,
                server_ip=server_ip,
            )
        else:
            logger.info("Playlist finished for player %s", player_id)

    def suppress_track_finished_for_player(self, player_mac: str, seconds: float = 1.0) -> None:
        """
        Temporarily suppress STMu-based auto-advance for a player.

        Call this right before/after starting a new track explicitly (manual user action),
        so a late STMu from the previous stream can't advance the playlist.

        Args:
            player_mac: Player MAC address.
            seconds: Suppression window duration.
        """
        until = asyncio.get_running_loop().time() + seconds
        self._suppress_track_finished_until[player_mac] = until
