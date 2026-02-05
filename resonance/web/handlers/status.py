"""
Status Command Handlers.

Handles server and player status commands:
- serverstatus: Server information and statistics
- players: List of connected players
- player: Player information by index
- status: Current player status (track, position, mode)
- pref: Server preferences
- rescan: Trigger library rescan
- wipecache: Clear library cache

PERF / RELIABILITY NOTE:
`status` is polled frequently by clients (e.g. Cadence ~1 Hz). It MUST remain fast.

In particular, generating BlurHash placeholders on-demand can be expensive (artwork extraction,
image decoding, hashing) and must NOT block the status response, otherwise clients will hit
HTTP timeouts during seeks/track transitions.

Therefore, we only include a BlurHash if it is already cached or cheaply accessible; otherwise
we skip it (and optionally let other background mechanisms populate caches).
"""

from __future__ import annotations

import logging
from typing import Any

from resonance.web.handlers import CommandContext
from resonance.web.jsonrpc_helpers import (
    build_list_response,
    build_player_item,
    build_track_item,
    get_filter_int,
    parse_start_items,
    parse_tagged_params,
    parse_tags_string,
)

logger = logging.getLogger(__name__)

VERSION = "0.1.0"


async def cmd_serverstatus(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'serverstatus' command.

    Returns server version and basic statistics, including players_loop.
    UI uses players_loop to auto-select a player when one connects.
    """
    # Get players
    players = await ctx.player_registry.get_all()
    player_count = len(players)

    # Build players_loop for UI compatibility
    players_loop = [build_player_item(p) for p in players]

    # Get library stats
    db = ctx.music_library._db
    artist_count = await db.count_artists()
    album_count = await db.count_albums()
    track_count = await db.count_tracks()

    return {
        "version": VERSION,
        "uuid": "resonance-server",
        "mac": "00:00:00:00:00:00",
        "info total albums": album_count,
        "info total artists": artist_count,
        "info total songs": track_count,
        "info total genres": 0,  # TODO: count genres
        "player count": player_count,
        "players_loop": players_loop,
        "other player count": 0,
        "sn player count": 0,
    }


async def cmd_players(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'players' command.

    Returns list of connected players.
    """
    start, items = parse_start_items(params)

    all_players = await ctx.player_registry.get_all()
    total_count = len(all_players)

    # Apply pagination
    paginated = all_players[start : start + items]

    players_loop = [build_player_item(p) for p in paginated]

    return build_list_response(players_loop, total_count, "players_loop")


async def cmd_player(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'player' command.

    Returns information about a specific player by index or MAC.
    """
    if len(params) < 2:
        return {"error": "Missing player index or parameter"}

    subcommand = params[1] if len(params) > 1 else ""

    if subcommand == "count":
        players = await ctx.player_registry.get_all()
        return {"_count": len(players)}

    if subcommand in ("id", "uuid", "name", "ip", "model", "displaytype"):
        # Get player by index
        player_idx = get_filter_int({"idx": params[2] if len(params) > 2 else "0"}, "idx")
        if player_idx is None:
            player_idx = 0

        players = await ctx.player_registry.get_all()
        if player_idx >= len(players):
            return {"error": "Player not found"}

        player = players[player_idx]

        if subcommand == "id":
            return {"_id": player.mac_address}
        elif subcommand == "uuid":
            return {"_uuid": player.mac_address}
        elif subcommand == "name":
            return {"_name": player.name}
        elif subcommand == "ip":
            return {"_ip": getattr(player, "ip_address", "0.0.0.0")}
        elif subcommand == "model":
            model = (
                getattr(player.info, "device_type", "squeezebox").name.lower()
                if hasattr(player, "info")
                else "squeezebox"
            )
            return {"_model": model}
        elif subcommand == "displaytype":
            return {"_displaytype": "none"}

    return {"error": f"Unknown player subcommand: {subcommand}"}


async def cmd_status(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'status' command.

    Returns current player status including:
    - Current track info
    - Playback position
    - Mode (play/pause/stop)
    - Volume
    - Playlist info
    """
    tagged_params = parse_tagged_params(params)
    tags_str = tagged_params.get("tags", "")
    tags = parse_tags_string(tags_str) if tags_str else None

    # Get player
    player = None
    if ctx.player_id != "-":
        player = await ctx.player_registry.get_by_mac(ctx.player_id)

    # Base status
    result: dict[str, Any] = {
        "player_connected": 1 if player else 0,
        "power": 1 if player else 0,
    }

    # Attach stream generation for discontinuity detection on polling clients.
    # This increments whenever a new stream is queued and allows clients to
    # ignore stale/foreign status samples.
    if ctx.streaming_server is not None:
        try:
            gen = ctx.streaming_server.get_stream_generation(ctx.player_id)
        except Exception:
            gen = None
        if gen is not None:
            result["stream_generation"] = gen

    if player is None:
        result["mode"] = "stop"
        result["time"] = 0
        result["duration"] = 0
        result["playlist_tracks"] = 0
        result["playlist_loop"] = []
        return result

    # Get player status
    status = player.status

    # Map state to LMS mode format
    state_to_mode = {
        "PLAYING": "play",
        "PAUSED": "pause",
        "STOPPED": "stop",
        "DISCONNECTED": "stop",
        "BUFFERING": "play",
    }
    state_name = status.state.name if hasattr(status.state, "name") else "STOPPED"
    result["mode"] = state_to_mode.get(state_name, "stop")

    # Playback position and volume
    #
    # LMS-style elapsed calculation (from StreamingController.pm):
    #   songtime = startOffset + songElapsedSeconds
    #
    # After a seek to position X, the player reports elapsed time relative to
    # the NEW stream start (0, 1, 2, 3...). The real track position is:
    #   actual_elapsed = start_offset + raw_elapsed
    #
    # Example: Seek to 30s → player reports 0,1,2,3... → we return 30,31,32,33...
    #
    # NO HEURISTICS needed - this is exactly how LMS does it.
    # The start_offset is set when queuing a seek and cleared when a new track starts.

    # Get raw elapsed from player (relative to stream start after seek)
    # Prefer elapsed_milliseconds for precision when available.
    raw_elapsed_sec: float
    if hasattr(status, "elapsed_milliseconds") and status.elapsed_milliseconds > 0:
        raw_elapsed_sec = status.elapsed_milliseconds / 1000.0
    else:
        raw_elapsed_sec = float(getattr(status, "elapsed_seconds", 0.0) or 0.0)

    # Get start offset from streaming server (LMS-style startOffset)
    start_offset: float = 0.0
    if ctx.streaming_server is not None:
        try:
            start_offset = ctx.streaming_server.get_start_offset(ctx.player_id)
        except Exception:
            start_offset = 0.0

    # Get duration for capping
    duration_sec = status.duration_seconds if hasattr(status, "duration_seconds") else 0.0

    # Calculate actual elapsed: start_offset + raw_elapsed (LMS formula)
    elapsed_sec = start_offset + raw_elapsed_sec

    # Cap elapsed to duration (never show more than 100% progress)
    if duration_sec > 0 and elapsed_sec > duration_sec:
        elapsed_sec = duration_sec

    result["time"] = elapsed_sec
    result["duration"] = status.duration_seconds if hasattr(status, "duration_seconds") else 0
    result["mixer volume"] = status.volume
    result["rate"] = 1 if result["mode"] == "play" else 0

    # Playlist info
    playlist_loop: list[dict[str, Any]] = []

    if ctx.playlist_manager is not None:
        playlist = ctx.playlist_manager.get(ctx.player_id)
        if playlist is not None:
            result["playlist_tracks"] = len(playlist)
            # LMS clients commonly rely on "playlist index" (not "playlist_cur_index")
            # and need current track info to match that index.
            result["playlist_cur_index"] = playlist.current_index
            result["playlist index"] = playlist.current_index
            result["playlist shuffle"] = 1 if playlist.shuffle_mode.value else 0
            result["playlist repeat"] = playlist.repeat_mode.value

            # Get current track info
            current = playlist.current_track
            if current is not None:
                result["duration"] = (current.duration_ms or 0) / 1000.0
                server_url = f"http://{ctx.server_host}:{ctx.server_port}"

                # Expose current track in a stable shape so the UI can highlight correctly.
                # Note: keep keys aligned with the Track shape used by the web-ui.
                track_id = getattr(current, "id", getattr(current, "track_id", None))
                album_id = getattr(current, "album_id", None)
                artist = getattr(current, "artist_name", getattr(current, "artist", ""))
                album = getattr(current, "album_title", getattr(current, "album", ""))
                duration_ms = getattr(current, "duration_ms", 0)
                path = getattr(current, "path", "")

                # Also expose a top-level track id so polling clients can detect
                # track changes even if `currentTrack` is missing/partial temporarily.
                result["track_id"] = track_id

                result["currentTrack"] = {
                    "id": track_id,
                    "title": getattr(current, "title", ""),
                    "artist": artist or "",
                    "album": album or "",
                    "duration": (duration_ms or 0) / 1000.0,
                    "path": path,
                    "coverArt": f"{server_url}/artwork/{album_id}" if album_id else "",
                }

                # Add BlurHash if available — MUST NOT BLOCK status polling.
                #
                # Important: get_blurhash() may extract artwork + decode images + compute hash.
                # That can exceed client HTTP timeouts (especially around seeks/stream restarts).
                #
                # We therefore only include blurhash if it can be obtained without expensive
                # on-demand generation. If the ArtworkManager doesn't provide a cheap path,
                # we skip blurhash here.
                if ctx.artwork_manager and path:
                    try:
                        # Prefer a non-blocking / cache-only method if available.
                        # Use the fast cached-only method when available.
                        # Call it directly so type-checkers see an awaitable coroutine.
                        if hasattr(ctx.artwork_manager, "get_blurhash_if_cached"):
                            blurhash = await ctx.artwork_manager.get_blurhash_if_cached(path)
                            if blurhash:
                                result["currentTrack"]["blurhash"] = blurhash
                        else:
                            # Fallback: do NOT call get_blurhash() here (can be slow).
                            pass
                    except Exception:
                        pass

                # Build track info for playlist_loop
                # Get the first N tracks based on params
                start = 0
                items = 1  # Default to just current track

                # Check for "-" which means current track only
                if len(params) >= 2:
                    if params[1] == "-":
                        # "-" means start from current track
                        start = playlist.current_index
                        items = 1
                    else:
                        start, items = parse_start_items(["status", params[1]] + list(params[2:]))

                # Get tracks for playlist_loop
                tracks = list(playlist.tracks)[start : start + items]

                for i, track in enumerate(tracks):
                    track_id = getattr(track, "id", getattr(track, "track_id", None))
                    album_id = getattr(track, "album_id", None)
                    artist = getattr(track, "artist_name", getattr(track, "artist", ""))
                    album = getattr(track, "album_title", getattr(track, "album", ""))
                    duration_ms = getattr(track, "duration_ms", 0)
                    path = getattr(track, "path", "")

                    track_dict = {
                        "id": track_id,
                        "title": getattr(track, "title", ""),
                        "artist": artist or "",
                        "album": album or "",
                        "duration": (duration_ms or 0) / 1000.0,
                        "url": f"{server_url}/stream.mp3?track_id={track_id}",
                        "coverArt": f"{server_url}/artwork/{album_id}" if album_id else "",
                        "playlist index": start + i,
                    }

                    # Add BlurHash for tracks in the loop
                    if ctx.artwork_manager and path:
                        try:
                            track_dict["blurhash"] = await ctx.artwork_manager.get_blurhash(path)
                        except Exception:
                            pass

                    # Add optional fields based on tags
                    if tags is None or "n" in tags:
                        if track.track_no:
                            track_dict["tracknum"] = track.track_no
                    if tags is None or "i" in tags:
                        if track.disc_no:
                            track_dict["disc"] = track.disc_no
                    if tags is None or "y" in tags:
                        if track.year:
                            track_dict["year"] = track.year

                    playlist_loop.append(track_dict)
        else:
            result["playlist_tracks"] = 0
            result["playlist_cur_index"] = 0
            result["playlist shuffle"] = 0
            result["playlist repeat"] = 0
    else:
        result["playlist_tracks"] = 0

    result["playlist_loop"] = playlist_loop

    return result


async def cmd_pref(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'pref' command.

    Returns server preferences.
    """
    if len(params) < 2:
        return {"error": "Missing preference name"}

    pref_name = params[1]

    # Handle mediadirs preference (music folders)
    if pref_name == "mediadirs":
        if len(params) >= 3 and params[2] == "?":
            # Query music folders
            folders = await ctx.music_library.get_music_folders()
            return {"_p2": ";".join(folders)}

        elif len(params) >= 3:
            # Set music folders
            folders_str = params[2]
            if folders_str:
                folders = folders_str.split(";")
                await ctx.music_library.set_music_folders(folders)
            return {"_p2": folders_str}

    # Handle other preferences
    pref_defaults: dict[str, Any] = {
        "language": "en",
        "audiodir": "",
        "playlistdir": "",
        "httpport": ctx.server_port,
    }

    if len(params) >= 3 and params[2] == "?":
        return {"_p2": pref_defaults.get(pref_name, "")}

    return {}


async def cmd_rescan(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'rescan' command.

    Triggers a library rescan.
    """
    tagged_params = parse_tagged_params(params)

    # Check if this is a progress query
    if "?" in params:
        status = ctx.music_library.get_scan_status()
        return {
            "rescan": 1 if status.is_running else 0,
            "progressname": status.current_folder,
            "progressdone": status.folders_done,
            "progresstotal": status.folders_total,
        }

    # Start rescan
    await ctx.music_library.start_scan()

    return {"rescan": 1}


async def cmd_wipecache(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'wipecache' command.

    Clears the library cache and rescans.
    """
    # Clear database
    await ctx.music_library._db.clear_all()

    # Start fresh scan
    await ctx.music_library.start_scan()

    return {"wipecache": 1}
