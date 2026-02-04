"""
HTTP Streaming Server for Resonance.

This module provides audio streaming functionality for Squeezebox players.
When a player receives a 'strm' command, it connects back to the HTTP server
to receive the audio data.

IMPORTANT: This class does NOT bind its own port. The streaming endpoint
is exposed via FastAPI routes (see web/routes/streaming.py). This avoids
port conflicts with the main web server.

STREAM CANCELLATION:
====================
When a player changes tracks, we need to cancel the current HTTP stream
immediately so the new track can start without delay. This is done via
CancellationTokens - each stream checks its token and aborts if cancelled.
This mimics LMS's closeStream() + forgetClient() behavior.
"""

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


class CancellationToken:
    """
    Token to signal stream cancellation.

    When a player changes tracks, we set cancelled=True on their token.
    The streaming generator checks this and aborts, allowing the new
    stream to start immediately without waiting for buffer drain.
    """

    __slots__ = ("_cancelled", "_generation")

    def __init__(self, generation: int = 0) -> None:
        self._cancelled = False
        self._generation = generation

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def generation(self) -> int:
        return self._generation

    def cancel(self) -> None:
        self._cancelled = True


# Buffer size for streaming
STREAM_BUFFER_SIZE = 65536  # 64KB chunks


class StreamingServer:
    """
    Audio streaming service for Squeezebox players.

    This class manages the queue of files to stream and provides
    methods to resolve which file to serve for a given player.

    NOTE: This class no longer binds its own socket. Instead, streaming
    is handled via FastAPI routes that call into this class.

    Attributes:
        port: The HTTP port where streaming is available (for strm command).
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9000,
        audio_provider: Callable[[str], Path | None] | None = None,
    ) -> None:
        """
        Initialize the streaming server.

        Args:
            host: Host address (kept for compatibility, not used for binding).
            port: HTTP port (used in strm command URL generation).
            audio_provider: Optional callback to resolve player MAC to audio file.
                           Takes player MAC, returns Path to audio file or None.
        """
        self.host = host
        self.port = port
        self._audio_provider = audio_provider
        self._running = False

        # Queue of files to stream, keyed by player MAC
        self._stream_queue: dict[str, Path] = {}

        # Seek positions for transcoded streams, keyed by player MAC
        # Values are (start_seconds, end_seconds or None)
        self._seek_positions: dict[str, tuple[float, float | None]] = {}

        # Byte offsets for direct-stream seeking, keyed by player MAC
        # Used for MP3/FLAC/OGG where we can seek by byte position
        self._byte_offsets: dict[str, int] = {}

        # Active stream cancellation tokens, keyed by player MAC
        # When a player changes tracks, we cancel the old token so the
        # streaming generator aborts immediately (LMS-style closeStream)
        self._stream_tokens: dict[str, CancellationToken] = {}

        # Generation counter per player to detect stale streams
        self._stream_generation: dict[str, int] = {}

    def cancel_stream(self, player_mac: str) -> None:
        """
        Cancel any active stream for a player.

        This should be called before starting a new track to ensure
        the old HTTP stream aborts immediately (LMS-style closeStream).

        Args:
            player_mac: MAC address of the player.
        """
        if player_mac in self._stream_tokens:
            old_token = self._stream_tokens[player_mac]
            old_token.cancel()
            logger.debug(
                "Cancelled stream for player %s (generation %d)", player_mac, old_token.generation
            )

    def get_cancellation_token(self, player_mac: str) -> CancellationToken:
        """
        Get the current cancellation token for a player's stream.

        The streaming route should check this token periodically and
        abort if cancelled. A new token is created each time a file
        is queued.

        Args:
            player_mac: MAC address of the player.

        Returns:
            The current CancellationToken for this player.
        """
        if player_mac not in self._stream_tokens:
            gen = self._stream_generation.get(player_mac, 0)
            self._stream_tokens[player_mac] = CancellationToken(gen)
        return self._stream_tokens[player_mac]

    def queue_file(self, player_mac: str, file_path: Path) -> None:
        """
        Queue an audio file to be streamed to a player.

        When the player connects with a GET request, this file will be served.
        This also cancels any existing stream and creates a new cancellation token.

        Args:
            player_mac: MAC address of the player.
            file_path: Path to the audio file to stream.
        """
        # Cancel any existing stream first (LMS-style closeStream)
        self.cancel_stream(player_mac)

        # Increment generation and create new token
        gen = self._stream_generation.get(player_mac, 0) + 1
        self._stream_generation[player_mac] = gen
        self._stream_tokens[player_mac] = CancellationToken(gen)

        self._stream_queue[player_mac] = file_path
        # Clear any previous seek position
        self._seek_positions.pop(player_mac, None)
        self._byte_offsets.pop(player_mac, None)
        logger.info("Queued %s for player %s (generation %d)", file_path.name, player_mac, gen)

    def queue_file_with_seek(
        self,
        player_mac: str,
        file_path: Path,
        start_seconds: float,
        end_seconds: float | None = None,
    ) -> None:
        """
        Queue an audio file with a seek position for transcoded streaming.

        This is used for M4B/M4A/MP4 files where we need to tell faad
        to start at a specific time position using -j and optionally -e.

        Args:
            player_mac: MAC address of the player.
            file_path: Path to the audio file to stream.
            start_seconds: Start position in seconds.
            end_seconds: Optional end position in seconds.
        """
        # Cancel any existing stream first (LMS-style closeStream)
        self.cancel_stream(player_mac)

        # Increment generation and create new token
        gen = self._stream_generation.get(player_mac, 0) + 1
        self._stream_generation[player_mac] = gen
        self._stream_tokens[player_mac] = CancellationToken(gen)

        self._stream_queue[player_mac] = file_path
        self._seek_positions[player_mac] = (start_seconds, end_seconds)
        self._byte_offsets.pop(player_mac, None)  # Clear byte offset when using time-based seek
        logger.info(
            "Queued %s for player %s with seek: start=%.1fs, end=%s (generation %d)",
            file_path.name,
            player_mac,
            start_seconds,
            f"{end_seconds:.1f}s" if end_seconds else "None",
            gen,
        )

    def get_seek_position(self, player_mac: str) -> tuple[float, float | None] | None:
        """
        Get the seek position for a player.

        Args:
            player_mac: MAC address of the player.

        Returns:
            Tuple of (start_seconds, end_seconds) or None if no seek position set.
        """
        return self._seek_positions.get(player_mac)

    def clear_seek_position(self, player_mac: str) -> None:
        """
        Clear the seek position for a player after streaming starts.

        Args:
            player_mac: MAC address of the player.
        """
        self._seek_positions.pop(player_mac, None)

    def queue_file_with_byte_offset(
        self,
        player_mac: str,
        file_path: Path,
        byte_offset: int,
    ) -> None:
        """
        Queue an audio file with a byte offset for direct streaming.

        This is used for MP3/FLAC/OGG files where we can seek by byte position.
        The byte offset is calculated from the seek time and file properties.

        Args:
            player_mac: MAC address of the player.
            file_path: Path to the audio file to stream.
            byte_offset: Starting byte offset in the file.
        """
        # Cancel any existing stream first (LMS-style closeStream)
        self.cancel_stream(player_mac)

        # Increment generation and create new token
        gen = self._stream_generation.get(player_mac, 0) + 1
        self._stream_generation[player_mac] = gen
        self._stream_tokens[player_mac] = CancellationToken(gen)

        self._stream_queue[player_mac] = file_path
        self._byte_offsets[player_mac] = byte_offset
        self._seek_positions.pop(player_mac, None)  # Clear time-based seek
        logger.info(
            "Queued %s for player %s with byte offset: %d (generation %d)",
            file_path.name,
            player_mac,
            byte_offset,
            gen,
        )

    def get_byte_offset(self, player_mac: str) -> int | None:
        """
        Get the byte offset for a player.

        Args:
            player_mac: MAC address of the player.

        Returns:
            Byte offset or None if not set.
        """
        return self._byte_offsets.get(player_mac)

    def clear_byte_offset(self, player_mac: str) -> None:
        """
        Clear the byte offset for a player after streaming starts.

        Args:
            player_mac: MAC address of the player.
        """
        self._byte_offsets.pop(player_mac, None)

    def dequeue_file(self, player_mac: str) -> Path | None:
        """
        Remove and return the queued file for a player.

        Args:
            player_mac: MAC address of the player.

        Returns:
            The queued file path, or None if nothing was queued.
        """
        return self._stream_queue.pop(player_mac, None)

    def get_queued_file(self, player_mac: str) -> Path | None:
        """
        Get the queued file for a player without removing it.

        Args:
            player_mac: MAC address of the player.

        Returns:
            The queued file path, or None if nothing was queued.
        """
        return self._stream_queue.get(player_mac)

    async def start(self) -> None:
        """
        Mark the streaming server as running.

        NOTE: This no longer binds a socket. The actual HTTP endpoint
        is provided by FastAPI routes.
        """
        if self._running:
            logger.warning("Streaming server already running")
            return

        self._running = True
        logger.info("Streaming server ready (via FastAPI on port %d)", self.port)

    async def stop(self) -> None:
        """Stop the streaming server."""
        if not self._running:
            return

        self._running = False

        # Cancel all active streams
        for player_mac in list(self._stream_tokens.keys()):
            self.cancel_stream(player_mac)

        self._stream_queue.clear()
        self._seek_positions.clear()
        self._byte_offsets.clear()
        self._stream_tokens.clear()
        self._stream_generation.clear()
        logger.info("Streaming server stopped")

    def resolve_file(self, player_mac: str | None) -> Path | None:
        """
        Resolve the file to stream for a player.

        This checks:
        1. The direct queue (files queued via queue_file)
        2. The audio_provider callback (e.g., PlaylistManager)

        Args:
            player_mac: MAC address of the player.

        Returns:
            Path to the audio file, or None if not found.
        """
        if not player_mac:
            logger.debug("resolve_file: no player_mac provided")
            return None

        # First check the queue
        if player_mac in self._stream_queue:
            queued = self._stream_queue.get(player_mac)
            logger.info(
                "resolve_file: player=%s -> FROM QUEUE: %s",
                player_mac,
                queued.name if queued else None,
            )
            return queued

        # Then try the audio provider callback
        if self._audio_provider:
            from_provider = self._audio_provider(player_mac)
            logger.info(
                "resolve_file: player=%s -> FROM PROVIDER (playlist.current_track): %s",
                player_mac,
                from_provider.name if from_provider else None,
            )
            return from_provider

        logger.warning("resolve_file: player=%s -> NO FILE FOUND", player_mac)
        return None

    @staticmethod
    def get_content_type(file_path: Path) -> str:
        """Get MIME type for a file."""
        suffix = file_path.suffix.lower()

        # Common audio types
        audio_types = {
            ".mp3": "audio/mpeg",
            ".flac": "audio/flac",
            ".ogg": "audio/ogg",
            ".wav": "audio/wav",
            ".aac": "audio/aac",
            ".m4a": "audio/mp4",
            ".m4b": "audio/m4a",  # Audiobook format (AAC in MP4 container)
            ".wma": "audio/x-ms-wma",
            ".aif": "audio/aiff",
            ".aiff": "audio/aiff",
            ".opus": "audio/opus",
        }

        if suffix in audio_types:
            return audio_types[suffix]

        # Fall back to mimetypes
        content_type, _ = mimetypes.guess_type(str(file_path))
        return content_type or "application/octet-stream"

    @staticmethod
    def parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int]:
        """
        Parse HTTP Range header.

        Args:
            range_header: The Range header value (e.g., "bytes=0-1024").
            file_size: Total size of the file.

        Returns:
            Tuple of (start_byte, end_byte).
        """
        start_byte = 0
        end_byte = file_size - 1

        if range_header and range_header.startswith("bytes="):
            try:
                range_spec = range_header[6:]  # Remove "bytes="
                if "-" in range_spec:
                    start_str, end_str = range_spec.split("-", 1)
                    if start_str:
                        start_byte = int(start_str)
                    if end_str:
                        end_byte = int(end_str)
            except ValueError:
                pass

        # Clamp range
        start_byte = max(0, min(start_byte, file_size - 1))
        end_byte = max(start_byte, min(end_byte, file_size - 1))

        return start_byte, end_byte

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running

    @property
    def buffer_size(self) -> int:
        """Get the buffer size for streaming."""
        return STREAM_BUFFER_SIZE
