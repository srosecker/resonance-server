"""
Playlist Command Handlers.

Handles playlist management commands:
- playlist play: Play a track by index or load a new playlist
- playlist add: Add tracks to the playlist
- playlist insert: Insert tracks at a position
- playlist delete: Remove tracks from the playlist
- playlist clear: Clear the playlist
- playlist move: Move a track to a new position
- playlist index: Jump to a track by index
- playlist shuffle: Toggle or set shuffle mode
- playlist repeat: Set repeat mode (off/one/all)
- playlist tracks: Get playlist track info
- playlist loadtracks: Load tracks into playlist
- playlist jump: Relative navigation (+1/-1 for next/previous)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from resonance.core.db.models import TrackRow
from resonance.web.handlers import CommandContext
from resonance.web.jsonrpc_helpers import (
    get_filter_int,
    parse_start_items,
    parse_tagged_params,
    to_dict,
)

logger = logging.getLogger(__name__)


async def cmd_playlist(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist' command.

    Dispatches to sub-handlers based on the subcommand.
    """
    if len(params) < 2:
        return {"error": "Missing playlist subcommand"}

    subcommand = str(params[1]).lower()

    handlers = {
        "play": _playlist_play,
        "add": _playlist_add,
        "insert": _playlist_insert,
        "delete": _playlist_delete,
        "clear": _playlist_clear,
        "move": _playlist_move,
        "index": _playlist_index,
        "shuffle": _playlist_shuffle,
        "repeat": _playlist_repeat,
        "tracks": _playlist_tracks,
        "loadtracks": _playlist_loadtracks,
        "jump": _playlist_jump,
    }

    handler = handlers.get(subcommand)
    if handler is None:
        return {"error": f"Unknown playlist subcommand: {subcommand}"}

    return await handler(ctx, params)


async def _playlist_play(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist play' - play a track by index or start playback.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"error": "Player not found"}

    if ctx.playlist_manager is None:
        logger.warning("playlist_manager not available")
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"error": "No playlist for player"}

    # Get track index if provided
    if len(params) >= 3:
        try:
            index = int(params[2])
            track = playlist.play(index)
        except (ValueError, TypeError):
            # Not an index, might be a track ID or path
            track = playlist.current_track
    else:
        track = playlist.current_track

    if track is None:
        return {"error": "No track to play"}

    # Start track stream
    await _start_track_stream(ctx, player, track)

    return {}


async def _playlist_add(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist add' - add tracks to the playlist.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        logger.warning("playlist_manager not available")
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)

    # Get track ID or path from params
    if len(params) < 3:
        return {"error": "Missing track to add"}

    track_ref = params[2]
    tagged_params = parse_tagged_params(params[3:])

    # Try to resolve track from database
    track = await _resolve_track(ctx, track_ref, tagged_params)
    if track is None:
        return {"error": f"Track not found: {track_ref}"}

    playlist.add(track)

    return {"count": len(playlist)}


async def _playlist_insert(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist insert' - insert tracks at a position.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)

    if len(params) < 3:
        return {"error": "Missing track to insert"}

    track_ref = params[2]
    tagged_params = parse_tagged_params(params[3:])

    # Get position (default to current index + 1)
    position = get_filter_int(tagged_params, "position")
    if position is None:
        position = playlist.current_index + 1

    track = await _resolve_track(ctx, track_ref, tagged_params)
    if track is None:
        return {"error": f"Track not found: {track_ref}"}

    playlist.insert(position, track)

    return {"count": len(playlist)}


async def _playlist_delete(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist delete' - remove tracks from the playlist.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"error": "No playlist for player"}

    if len(params) < 3:
        return {"error": "Missing index to delete"}

    try:
        index = int(params[2])
        playlist.remove(index)
        return {"count": len(playlist)}
    except (ValueError, TypeError, IndexError) as e:
        return {"error": str(e)}


async def _playlist_clear(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist clear' - clear the playlist.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is not None:
        playlist.clear()

    # Clearing the playlist should stop playback (LMS-like) and cancel any active stream.
    # Otherwise the player may continue playing buffered audio / stale stream.
    if ctx.streaming_server is not None:
        ctx.streaming_server.cancel_stream(ctx.player_id)

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is not None:
        await player.stop()
        if hasattr(player, "flush"):
            await player.flush()

    return {"count": 0}


async def _playlist_move(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist move' - move a track to a new position.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"error": "No playlist for player"}

    if len(params) < 4:
        return {"error": "Missing from and to indices"}

    try:
        from_idx = int(params[2])
        to_idx = int(params[3])
        playlist.move(from_idx, to_idx)
        return {"count": len(playlist)}
    except (ValueError, TypeError, IndexError) as e:
        return {"error": str(e)}


async def _playlist_index(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist index' - jump to a track by index.

    Supports:
    - playlist index ? : Query current index
    - playlist index <n> : Jump to absolute index
    - playlist index +1 : Next track
    - playlist index -1 : Previous track
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"_index": 0}

    # Query mode
    if len(params) < 3 or params[2] == "?":
        return {"_index": playlist.current_index}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)

    # Handle relative indices (+1, -1)
    index_str = str(params[2])
    if index_str == "+1":
        track = playlist.next()
        if track is not None and player is not None:
            await _start_track_stream(ctx, player, track)
        return {"_index": playlist.current_index}
    elif index_str == "-1":
        track = playlist.previous()
        if track is not None and player is not None:
            await _start_track_stream(ctx, player, track)
        return {"_index": playlist.current_index}

    # Absolute index
    try:
        index = int(index_str)
        track = playlist.play(index)
        if track is not None and player is not None:
            await _start_track_stream(ctx, player, track)
        return {"_index": playlist.current_index}
    except (ValueError, TypeError):
        return {"error": f"Invalid index: {index_str}"}


async def _playlist_shuffle(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist shuffle' - toggle or set shuffle mode.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"_shuffle": 0}

    # Query mode
    if len(params) < 3 or params[2] == "?":
        return {"_shuffle": playlist.shuffle_mode.value}

    # Set mode
    try:
        value = int(params[2])
        playlist.set_shuffle(value)
        return {"_shuffle": playlist.shuffle_mode.value}
    except (ValueError, TypeError):
        # Toggle
        new_value = 0 if playlist.shuffle_mode.value else 1
        playlist.set_shuffle(new_value)
        return {"_shuffle": playlist.shuffle_mode.value}


async def _playlist_repeat(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist repeat' - set repeat mode.

    Values:
    - 0: Off
    - 1: Repeat one
    - 2: Repeat all
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"_repeat": 0}

    # Query mode
    if len(params) < 3 or params[2] == "?":
        return {"_repeat": playlist.repeat_mode.value}

    # Set mode
    try:
        value = int(params[2])
        playlist.set_repeat(value)
        return {"_repeat": playlist.repeat_mode.value}
    except (ValueError, TypeError):
        return {"error": f"Invalid repeat value: {params[2]}"}


async def _playlist_tracks(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist tracks' - get playlist track info.
    """
    if ctx.player_id == "-":
        return {"count": 0, "tracks_loop": []}

    if ctx.playlist_manager is None:
        return {"count": 0, "tracks_loop": []}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"count": 0, "tracks_loop": []}

    start, items = parse_start_items(params)
    server_url = f"http://{ctx.server_host}:{ctx.server_port}"

    tracks_loop = []
    all_tracks = list(playlist.tracks)
    paginated = all_tracks[start : start + items]

    for i, track in enumerate(paginated):
        tracks_loop.append(
            {
                "id": track.id,
                "title": track.title,
                "artist": track.artist_name or "",
                "album": track.album_title or "",
                "duration": (track.duration_ms or 0) / 1000.0,
                "url": f"{server_url}/stream.mp3?track_id={track.id}",
                "playlist index": start + i,
            }
        )

    return {
        "count": len(all_tracks),
        "tracks_loop": tracks_loop,
    }


async def _playlist_loadtracks(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist loadtracks' - load tracks into playlist.

    Clears the existing playlist and loads new tracks.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    # Clear existing playlist
    playlist = ctx.playlist_manager.get(ctx.player_id)
    playlist.clear()

    # Parse track criteria from params
    tagged_params = parse_tagged_params(params)
    album_id = get_filter_int(tagged_params, "album_id")
    artist_id = get_filter_int(tagged_params, "artist_id")
    genre_id = get_filter_int(tagged_params, "genre_id")

    db = ctx.music_library._db

    # Load tracks based on criteria
    if album_id is not None:
        rows = await db.list_tracks_by_album(album_id=album_id, offset=0, limit=1000)
    elif artist_id is not None:
        rows = await db.list_tracks_by_artist(artist_id=artist_id, offset=0, limit=1000)
    elif genre_id is not None:
        rows = await db.list_tracks_by_genre_id(genre_id=genre_id, offset=0, limit=1000)
    else:
        return {"error": "No track criteria specified"}

    # Convert rows to Track objects and add to playlist
    from resonance.core.library import Track

    for row in rows:
        row_dict = to_dict(row)
        track = Track(
            id=row_dict.get("id"),
            path=row_dict.get("path", ""),
            title=row_dict.get("title", ""),
            artist_id=row_dict.get("artist_id"),
            album_id=row_dict.get("album_id"),
            artist_name=row_dict.get("artist_name"),
            album_title=row_dict.get("album_title"),
            year=row_dict.get("year"),
            duration_ms=row_dict.get("duration_ms"),
            disc_no=row_dict.get("disc_no"),
            track_no=row_dict.get("track_no"),
            compilation=row_dict.get("compilation", 0),
        )
        playlist.add(track)

    return {"count": len(playlist)}


async def _playlist_jump(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'playlist jump' - relative navigation.

    - playlist jump +1 : Next track
    - playlist jump -1 : Previous track
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    if ctx.playlist_manager is None:
        return {"error": "Playlist manager not available"}

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return {"error": "No playlist for player"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"error": "Player not found"}

    if len(params) < 3:
        return {"error": "Missing jump direction"}

    direction = str(params[2])
    track = None

    if direction in ("+1", "1"):
        track = playlist.next()
    elif direction == "-1":
        track = playlist.previous()
    else:
        return {"error": f"Invalid jump direction: {direction}"}

    if track is not None:
        await _start_track_stream(ctx, player, track)

    return {"_index": playlist.current_index}


# =============================================================================
# Helper Functions
# =============================================================================


async def _start_track_stream(
    ctx: CommandContext,
    player: Any,
    track: Any,
) -> None:
    """
    Start streaming a track to a player.

    Handles:
    1. Stream cancellation (stop old stream)
    2. Player stop/flush
    3. Set volume (audg must be sent before strm!)
    4. Queue new file
    5. Start new stream
    """
    if ctx.streaming_server is None or ctx.slimproto is None:
        return

    # Suppress track-finished for a short window to prevent race conditions
    if hasattr(ctx.slimproto, "_server") and hasattr(
        ctx.slimproto._server, "suppress_track_finished_for_player"
    ):
        ctx.slimproto._server.suppress_track_finished_for_player(ctx.player_id, seconds=6.0)

    # Cancel any existing stream
    ctx.streaming_server.cancel_stream(ctx.player_id)

    # Stop and flush player buffer
    await player.stop()
    if hasattr(player, "flush"):
        await player.flush()

    # CRITICAL: Set volume before stream start!
    # The player needs an audg command before strm, otherwise audio may be silent.
    # Use current volume from player status, default to 100 if not set.
    current_volume = getattr(player.status, "volume", 100)
    current_muted = getattr(player.status, "muted", False)
    await player.set_volume(current_volume, current_muted)

    # Queue the new file
    ctx.streaming_server.queue_file(ctx.player_id, Path(track.path))

    # Get server IP for player
    server_ip = ctx.server_host
    if hasattr(ctx.slimproto, "get_advertise_ip_for_player"):
        server_ip = ctx.slimproto.get_advertise_ip_for_player(player)

    # Start streaming
    await player.start_track(
        track,
        server_port=ctx.server_port,
        server_ip=server_ip,
    )


async def _resolve_track(
    ctx: CommandContext,
    track_ref: Any,
    tagged_params: dict[str, str],
) -> Any:
    """
    Resolve a track reference to a Track object.

    track_ref can be:
    - Integer track ID
    - String track ID
    - File path
    """
    from resonance.core.library import Track

    db = ctx.music_library._db

    # Try as track ID
    def _row_to_track(row: TrackRow) -> Track:
        """Convert a TrackRow dataclass to a Track object."""
        return Track(
            id=row.id,
            path=row.path,
            title=row.title or "",
            artist_id=row.artist_id,
            album_id=row.album_id,
            artist_name=row.artist,
            album_title=row.album,
            year=row.year,
            duration_ms=row.duration_ms,
            disc_no=row.disc_no,
            track_no=row.track_no,
            compilation=row.compilation,
        )

    # Try as track ID
    try:
        track_id = int(track_ref)
        row = await db.get_track_by_id(track_id)
        if row is not None:
            return _row_to_track(row)
    except (ValueError, TypeError):
        pass

    # Try as file path
    track_ref_str = str(track_ref)
    if track_ref_str.startswith("file://"):
        track_ref_str = track_ref_str[7:]

    row = await db.get_track_by_path(track_ref_str)
    if row is not None:
        return _row_to_track(row)

    return None
