"""
JSON-RPC Facade for Resonance.

This module provides the main JSON-RPC endpoint that dispatches commands
to the appropriate handler modules. It implements the LMS-compatible
JSON-RPC protocol used by iPeng, Squeezer, Material Skin, and other clients.

The facade pattern keeps this module thin - all command logic is in handlers/.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from resonance.web.handlers import CommandContext
from resonance.web.handlers.library import (
    cmd_albums,
    cmd_artists,
    cmd_genres,
    cmd_roles,
    cmd_search,
    cmd_titles,
)
from resonance.web.handlers.menu import (
    cmd_alarm_settings,
    cmd_browselibrary,
    cmd_date,
    cmd_firmwareupgrade,
    cmd_menu,
    cmd_menustatus,
    cmd_playerinfo,
    cmd_playlistcontrol,
    cmd_sleep_settings,
    cmd_sync_settings,
)
from resonance.web.handlers.playback import (
    cmd_button,
    cmd_mixer,
    cmd_mode,
    cmd_pause,
    cmd_play,
    cmd_power,
    cmd_stop,
)
from resonance.web.handlers.playlist import cmd_playlist
from resonance.web.handlers.seeking import cmd_time
from resonance.web.handlers.status import (
    cmd_player,
    cmd_players,
    cmd_pref,
    cmd_rescan,
    cmd_serverstatus,
    cmd_status,
    cmd_wipecache,
)
from resonance.web.jsonrpc_helpers import (
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_PARAMS,
    ERROR_METHOD_NOT_FOUND,
    build_error_response,
)

if TYPE_CHECKING:
    from resonance.core.artwork import ArtworkManager
    from resonance.core.library import MusicLibrary
    from resonance.core.playlist import PlaylistManager
    from resonance.player.registry import PlayerRegistry
    from resonance.protocol.slimproto import SlimprotoServer
    from resonance.streaming.server import StreamingServer

logger = logging.getLogger(__name__)

# Type alias for command handlers
CommandHandler = Callable[[CommandContext, list[Any]], Coroutine[Any, Any, dict[str, Any]]]

# Command dispatch table
COMMAND_HANDLERS: dict[str, CommandHandler] = {
    # Status commands
    "serverstatus": cmd_serverstatus,
    "players": cmd_players,
    "player": cmd_player,
    "status": cmd_status,
    "pref": cmd_pref,
    "rescan": cmd_rescan,
    "wipecache": cmd_wipecache,
    # Library browsing
    "artists": cmd_artists,
    "albums": cmd_albums,
    "titles": cmd_titles,
    "genres": cmd_genres,
    "roles": cmd_roles,
    "search": cmd_search,
    # Playback control
    "play": cmd_play,
    "pause": cmd_pause,
    "stop": cmd_stop,
    "mode": cmd_mode,
    "power": cmd_power,
    "mixer": cmd_mixer,
    "button": cmd_button,
    # Playlist management
    "playlist": cmd_playlist,
    # Seeking
    "time": cmd_time,
    # Jive menu system (for Squeezebox Controller/Touch/Boom/Radio)
    "menu": cmd_menu,
    "menustatus": cmd_menustatus,
    "browselibrary": cmd_browselibrary,
    "playlistcontrol": cmd_playlistcontrol,
    "date": cmd_date,
    "alarmsettings": cmd_alarm_settings,
    "sleepsettings": cmd_sleep_settings,
    "syncsettings": cmd_sync_settings,
    "firmwareupgrade": cmd_firmwareupgrade,
    "playerinfo": cmd_playerinfo,
}


class JsonRpcHandler:
    """
    JSON-RPC request handler.

    Manages command dispatch and context creation for LMS-compatible
    JSON-RPC requests.
    """

    def __init__(
        self,
        music_library: MusicLibrary,
        player_registry: PlayerRegistry,
        playlist_manager: PlaylistManager | None = None,
        streaming_server: StreamingServer | None = None,
        slimproto: SlimprotoServer | None = None,
        artwork_manager: ArtworkManager | None = None,
        server_host: str = "127.0.0.1",
        server_port: int = 9000,
        server_uuid: str = "resonance",
    ) -> None:
        self.music_library = music_library
        self.player_registry = player_registry
        self.playlist_manager = playlist_manager
        self.streaming_server = streaming_server
        self.slimproto = slimproto
        self.artwork_manager = artwork_manager
        self.server_host = server_host
        self.server_port = server_port
        self.server_uuid = server_uuid

    async def handle_request(
        self,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle a JSON-RPC request.

        Args:
            request: The JSON-RPC request object with id, method, and params.

        Returns:
            JSON-RPC response object.
        """
        request_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", [])

        # Build base response
        response: dict[str, Any] = {
            "id": request_id,
            "method": method,
            "params": params,
        }

        # Handle slim.request method (LMS JSON-RPC format)
        if method == "slim.request":
            if not isinstance(params, list) or len(params) < 2:
                response["error"] = build_error_response(
                    ERROR_INVALID_PARAMS,
                    "slim.request requires [player_id, command_array]",
                )
                return response

            player_id = params[0]
            command = params[1]

            if not isinstance(command, list) or len(command) == 0:
                response["error"] = build_error_response(
                    ERROR_INVALID_PARAMS,
                    "Command must be a non-empty array",
                )
                return response

            try:
                result = await self.execute_command(player_id, command)
                response["result"] = result
            except Exception as e:
                logger.exception("Error executing command %s: %s", command, e)
                response["error"] = build_error_response(
                    ERROR_INTERNAL_ERROR,
                    str(e),
                )
        else:
            response["error"] = build_error_response(
                ERROR_METHOD_NOT_FOUND,
                f"Unknown method: {method}",
            )

        return response

    async def execute_command(
        self,
        player_id: str,
        command: list[Any],
    ) -> dict[str, Any]:
        """
        Execute a single LMS command.

        Args:
            player_id: Player MAC address (or "-" for server commands)
            command: Command array [command_name, arg1, arg2, ...]

        Returns:
            Command result dictionary
        """
        if not command:
            return {"error": "Empty command"}

        command_name = str(command[0]).lower()

        # Look up handler
        handler = COMMAND_HANDLERS.get(command_name)
        if handler is None:
            logger.warning("Unknown command: %s", command_name)
            return {"error": f"Unknown command: {command_name}"}

        # Build context
        ctx = CommandContext(
            player_id=player_id,
            music_library=self.music_library,
            player_registry=self.player_registry,
            playlist_manager=self.playlist_manager,
            streaming_server=self.streaming_server,
            slimproto=self.slimproto,
            artwork_manager=self.artwork_manager,
            server_host=self.server_host,
            server_port=self.server_port,
            server_uuid=self.server_uuid,
        )

        # Execute handler
        try:
            result = await handler(ctx, command)
            return result
        except Exception as e:
            logger.exception("Handler error for %s: %s", command_name, e)
            return {"error": str(e)}

    async def __call__(
        self,
        player_id: str,
        command: list[Any],
    ) -> dict[str, Any]:
        """
        Callable interface for Cometd /slim/request support.

        Args:
            player_id: Player MAC address
            command: Command array

        Returns:
            Command result
        """
        return await self.execute_command(player_id, command)
