"""
JSON-RPC Command Handlers Package.

This package contains the handler modules for JSON-RPC commands.
Each module handles a specific category of commands.

Modules:
- library: artists, albums, titles, genres, roles, search
- playback: play, pause, stop, mode, power, mixer, button
- playlist: playlist command (play, add, clear, index, shuffle, etc.)
- seeking: time, perform_seek, calculate_byte_offset
- status: serverstatus, players, player, status, pref, rescan, wipecache
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from resonance.core.artwork import ArtworkManager
    from resonance.core.library import MusicLibrary
    from resonance.core.playlist import PlaylistManager
    from resonance.player.registry import PlayerRegistry
    from resonance.protocol.slimproto import SlimprotoServer
    from resonance.streaming.server import StreamingServer


@dataclass
class CommandContext:
    """
    Context object passed to all command handlers.

    Contains references to all server components needed to process commands.
    This enables handlers to be stateless functions that receive all
    dependencies via this context.
    """

    player_id: str
    """The player MAC address (or '-' for server-level commands)."""

    music_library: MusicLibrary
    """The music library for browsing and searching."""

    player_registry: PlayerRegistry
    """Registry of connected players."""

    playlist_manager: PlaylistManager | None = None
    """Per-player playlist management."""

    streaming_server: StreamingServer | None = None
    """Streaming server for queueing files."""

    slimproto: SlimprotoServer | None = None
    """Slimproto server for player control commands."""

    artwork_manager: ArtworkManager | None = None
    """Artwork extraction and caching."""

    server_host: str = "127.0.0.1"
    """Server hostname for generating URLs."""

    server_port: int = 9000
    """Server port for generating URLs."""

    server_uuid: str = "resonance"
    """Server UUID for identification (full UUID v4, 36 chars with dashes)."""

    def __post_init__(self) -> None:
        if self.server_host == "0.0.0.0":
            self.server_host = "127.0.0.1"

    def get_player_url(self, path: str) -> str:
        """Generate a URL for player-accessible resources."""
        return f"http://{self.server_host}:{self.server_port}{path}"


__all__ = ["CommandContext"]
