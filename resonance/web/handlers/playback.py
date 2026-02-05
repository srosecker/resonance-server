"""
Playback Command Handlers.

Handles player control commands:
- play: Start/resume playback
- pause: Pause playback (toggle or explicit)
- stop: Stop playback
- mode: Query or set playback mode
- power: Query or set player power state
- mixer: Volume and audio controls
- button: Simulate remote control buttons
"""

from __future__ import annotations

import logging
from typing import Any

from resonance.web.handlers import CommandContext

logger = logging.getLogger(__name__)


async def cmd_play(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'play' command.

    LMS-like behavior:
    - If the player is STOPPED and there is a non-empty playlist, start streaming
      the current playlist item (queue playback).
    - Otherwise, resume/unpause via player.play().
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"error": "Player not found"}

    # If we're stopped and have a playlist, start the current track stream explicitly.
    try:
        playlist = None
        if ctx.playlist_manager is not None:
            playlist = ctx.playlist_manager.get(ctx.player_id)

        state_name = (
            player.status.state.name
            if hasattr(player, "status")
            and hasattr(player.status, "state")
            and hasattr(player.status.state, "name")
            else "STOPPED"
        )
        is_stopped = state_name in ("STOPPED", "DISCONNECTED")

        if playlist is not None and len(playlist) > 0 and is_stopped:
            # Avoid top-level import to prevent circular imports
            from resonance.web.handlers.playlist import _start_track_stream

            track = playlist.play(playlist.current_index)
            if track is not None:
                logger.info(
                    "[cmd_play] STOPPED -> starting stream from playlist",
                    extra={
                        "player_id": ctx.player_id,
                        "index": playlist.current_index,
                        "track_id": getattr(track, "id", None),
                    },
                )
                await _start_track_stream(ctx, player, track)
                return {}
    except Exception:
        logger.exception("[cmd_play] Failed to start from playlist, falling back to resume")

    await player.play()
    return {}


async def cmd_pause(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'pause' command.

    Pauses playback. Optional parameter:
    - 0: Resume (unpause)
    - 1: Pause
    - (none): Toggle
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"error": "Player not found"}

    # Check for explicit pause/unpause value
    if len(params) >= 2:
        try:
            pause_val = int(params[1])
            if pause_val == 0:
                await player.play()  # Unpause
            else:
                await player.pause()
        except (ValueError, TypeError):
            # Invalid value, just toggle
            await player.pause()
    else:
        # Toggle pause
        await player.pause()

    return {}


async def cmd_stop(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'stop' command.

    Stops playback on the player.
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"error": "Player not found"}

    await player.stop()

    return {}


async def cmd_mode(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'mode' command.

    Query or set the playback mode.
    - mode ? : Returns current mode
    - mode play : Start playing
    - mode pause : Pause
    - mode stop : Stop
    """
    if ctx.player_id == "-":
        return {"_mode": "stop"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"_mode": "stop"}

    # Query mode
    if len(params) < 2 or params[1] == "?":
        status = player.status
        state_to_mode = {
            "PLAYING": "play",
            "PAUSED": "pause",
            "STOPPED": "stop",
            "DISCONNECTED": "stop",
            "BUFFERING": "play",
        }
        state_name = status.state.name if hasattr(status.state, "name") else "STOPPED"
        return {"_mode": state_to_mode.get(state_name, "stop")}

    # Set mode
    new_mode = params[1].lower()
    if new_mode == "play":
        await player.play()
    elif new_mode == "pause":
        await player.pause()
    elif new_mode == "stop":
        await player.stop()

    return {"_mode": new_mode}


async def cmd_power(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'power' command.

    Query or set the player power state.
    - power ? : Returns current power state
    - power 0 : Power off
    - power 1 : Power on
    """
    if ctx.player_id == "-":
        return {"_power": 0}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"_power": 0}

    # Query power
    if len(params) < 2 or params[1] == "?":
        # Players are always "on" when connected
        return {"_power": 1}

    # Set power
    try:
        power_val = int(params[1])
        if power_val == 0:
            # Power off - stop playback and disable audio outputs
            await player.stop()
            await player.set_audio_enable(False)
        else:
            # Power on - enable audio outputs
            await player.set_audio_enable(True)
        return {"_power": power_val}
    except (ValueError, TypeError):
        return {"_power": 1}


async def cmd_mixer(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'mixer' command.

    Controls volume and other audio settings.
    - mixer volume ? : Query volume
    - mixer volume <n> : Set absolute volume (0-100)
    - mixer volume +<n> : Increase volume
    - mixer volume -<n> : Decrease volume
    - mixer muting ? : Query mute state
    - mixer muting 0/1 : Set mute state
    - mixer muting toggle : Toggle mute
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"error": "Player not found"}

    if len(params) < 2:
        return {"error": "Missing mixer subcommand"}

    subcommand = params[1].lower()

    if subcommand == "volume":
        current_volume = player.status.volume

        # Query volume
        if len(params) < 3 or params[2] == "?":
            return {"_volume": current_volume}

        # Set volume
        volume_str = str(params[2])

        try:
            if volume_str.startswith("+"):
                # Relative increase
                delta = int(volume_str[1:])
                new_volume = min(100, current_volume + delta)
            elif volume_str.startswith("-"):
                # Relative decrease
                delta = int(volume_str[1:])
                new_volume = max(0, current_volume - delta)
            else:
                # Absolute value
                new_volume = int(volume_str)
                new_volume = max(0, min(100, new_volume))

            await player.set_volume(new_volume)
            return {"_volume": new_volume}
        except (ValueError, TypeError):
            return {"error": f"Invalid volume value: {volume_str}"}

    elif subcommand == "muting":
        # Query mute state
        if len(params) < 3 or params[2] == "?":
            muted = getattr(player.status, "muted", False)
            return {"_muting": 1 if muted else 0}

        # Set mute state
        mute_val = params[2]
        if mute_val == "toggle":
            current_muted = getattr(player.status, "muted", False)
            # Toggle mute (if supported)
            if hasattr(player, "set_mute"):
                await player.set_mute(not current_muted)
            return {"_muting": 0 if current_muted else 1}
        else:
            try:
                mute_int = int(mute_val)
                if hasattr(player, "set_mute"):
                    await player.set_mute(mute_int == 1)
                return {"_muting": mute_int}
            except (ValueError, TypeError):
                return {"error": f"Invalid muting value: {mute_val}"}

    elif subcommand == "bass":
        # Bass control (not implemented, return default)
        if len(params) < 3 or params[2] == "?":
            return {"_bass": 0}
        return {"_bass": 0}

    elif subcommand == "treble":
        # Treble control (not implemented, return default)
        if len(params) < 3 or params[2] == "?":
            return {"_treble": 0}
        return {"_treble": 0}

    return {"error": f"Unknown mixer subcommand: {subcommand}"}


async def cmd_button(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'button' command.

    Simulates remote control button presses.
    Common buttons: play, pause, stop, fwd, rew, volup, voldown, mute
    """
    if ctx.player_id == "-":
        return {"error": "No player specified"}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"error": "Player not found"}

    if len(params) < 2:
        return {"error": "Missing button name"}

    button = params[1].lower()

    # Map button names to actions
    if button == "play":
        await player.play()
    elif button == "pause":
        await player.pause()
    elif button == "stop":
        await player.stop()
    elif button in ("fwd", "jump_fwd", "fwd.single"):
        # Skip forward
        if ctx.playlist_manager is not None:
            playlist = ctx.playlist_manager.get(ctx.player_id)
            if playlist is not None:
                next_track = playlist.next()
                if next_track is not None and ctx.streaming_server is not None:
                    from pathlib import Path

                    ctx.streaming_server.queue_file(ctx.player_id, Path(next_track.path))
                    server_ip = ctx.server_host
                    await player.start_track(
                        next_track,
                        server_port=ctx.server_port,
                        server_ip=server_ip,
                    )
    elif button in ("rew", "jump_rew", "rew.single"):
        # Skip backward
        if ctx.playlist_manager is not None:
            playlist = ctx.playlist_manager.get(ctx.player_id)
            if playlist is not None:
                prev_track = playlist.previous()
                if prev_track is not None and ctx.streaming_server is not None:
                    from pathlib import Path

                    ctx.streaming_server.queue_file(ctx.player_id, Path(prev_track.path))
                    server_ip = ctx.server_host
                    await player.start_track(
                        prev_track,
                        server_port=ctx.server_port,
                        server_ip=server_ip,
                    )
    elif button == "volup":
        current = player.status.volume
        await player.set_volume(min(100, current + 5))
    elif button == "voldown":
        current = player.status.volume
        await player.set_volume(max(0, current - 5))
    elif button == "mute":
        if hasattr(player, "set_mute"):
            current_muted = getattr(player.status, "muted", False)
            await player.set_mute(not current_muted)

    return {}
