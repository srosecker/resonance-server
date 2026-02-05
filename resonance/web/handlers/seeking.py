"""
Seeking Command Handlers.

Handles time/position control commands:
- time: Query or set playback position
- perform_seek: Execute a seek operation
- calculate_byte_offset: Calculate byte offset for direct-stream seeking

Direct-stream seeking uses byte offset heuristics for MP3/FLAC/OGG.
Transcoded seeking uses faad's -j/-e parameters for M4B/M4A.

This module integrates with SeekCoordinator for:
- Latest-wins semantics (only the most recent seek executes)
- Coalescing of rapid seek requests during user scrubbing
- Safe subprocess termination to prevent asyncio race conditions

IMPORTANT (LMS-compat / Race protection):
Seeking is a user-initiated manual action. Any pending/deferred "track finished"
timers (e.g. from early STMd deferral) must be cancelled/ignored, otherwise a
late deferred track-finished can incorrectly auto-advance the playlist to the
next track right after a seek.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from resonance.streaming.seek_coordinator import get_seek_coordinator
from resonance.web.handlers import CommandContext

logger = logging.getLogger(__name__)

# Approximate bytes per second for various formats (conservative estimates)
FORMAT_BYTES_PER_SECOND: dict[str, int] = {
    "mp3": 24000,  # ~192 kbps
    "flac": 100000,  # ~800 kbps (varies widely)
    "ogg": 20000,  # ~160 kbps
    "wav": 176400,  # 44.1kHz 16-bit stereo
    "aiff": 176400,
    "aif": 176400,
}

# Formats that require transcoding for seeking (use time-based seeking)
TRANSCODE_SEEK_FORMATS = {".m4a", ".m4b", ".mp4", ".aac", ".alac"}


async def cmd_time(
    ctx: CommandContext,
    params: list[Any],
) -> dict[str, Any]:
    """
    Handle 'time' command.

    Query or set the playback position.
    - time ? : Returns current position in seconds
    - time <seconds> : Seek to absolute position
    - time +<seconds> : Seek forward
    - time -<seconds> : Seek backward

    Seeks are coordinated through SeekCoordinator for latest-wins semantics.

    NOTE (LMS-style semantics):
    This handler must be fast. Seeking can involve cancelling streams, stopping/flushing,
    restarting transcode pipelines, etc. Waiting for the full seek execution here can
    cause JSON-RPC timeouts on clients.

    Therefore, we schedule the coordinated seek asynchronously ("fire-and-forget") and
    immediately acknowledge the target time. Clients will observe the seek via polling
    (`status`) and/or subsequent STAT updates.
    """
    if ctx.player_id == "-":
        return {"_time": 0}

    player = await ctx.player_registry.get_by_mac(ctx.player_id)
    if player is None:
        return {"_time": 0}

    # Query mode
    if len(params) < 2 or params[1] == "?":
        elapsed = player.status.elapsed_seconds
        return {"_time": elapsed}

    # Parse seek target
    time_str = str(params[1])
    current_time = player.status.elapsed_seconds

    try:
        if time_str.startswith("+"):
            # Relative forward
            delta = float(time_str[1:])
            target_time = current_time + delta
        elif time_str.startswith("-"):
            # Relative backward
            delta = float(time_str[1:])
            target_time = current_time - delta
        else:
            # Absolute position
            target_time = float(time_str)
    except (ValueError, TypeError):
        return {"error": f"Invalid time value: {time_str}"}

    # Clamp to valid range
    target_time = max(0.0, target_time)

    # Get current track duration for clamping
    duration = 0.0
    if ctx.playlist_manager is not None:
        playlist = ctx.playlist_manager.get(ctx.player_id)
        if playlist is not None:
            current_track = playlist.current_track
            if current_track is not None and current_track.duration_ms:
                duration = current_track.duration_ms / 1000.0
                # Clamp to duration minus 1 second to avoid EOF issues
                target_time = min(target_time, max(0, duration - 1.0))

    # Use SeekCoordinator for latest-wins semantics
    coordinator = get_seek_coordinator()

    async def seek_executor(seek_target: float) -> None:
        await _execute_seek_internal(ctx, player, seek_target)

    async def run_seek() -> None:
        try:
            await coordinator.seek(ctx.player_id, target_time, seek_executor)
        except Exception:
            logger.exception(
                "Background seek failed for player %s (target=%.3fs)",
                ctx.player_id,
                target_time,
            )

    asyncio.create_task(run_seek())

    return {"_time": target_time}


async def perform_seek(
    ctx: CommandContext,
    player: Any,
    target_seconds: float,
) -> None:
    """
    Execute a seek operation through the SeekCoordinator.

    This is the public API for seek operations. It uses the SeekCoordinator
    for latest-wins semantics, ensuring that rapid seeks don't overwhelm
    the server with transcode pipeline restarts.

    For transcoded formats (M4B/M4A), uses time-based seeking via faad -j/-e.
    For direct-stream formats (MP3/FLAC/OGG), uses byte offset seeking.
    """
    coordinator = get_seek_coordinator()

    async def seek_executor(seek_target: float) -> None:
        await _execute_seek_internal(ctx, player, seek_target)

    await coordinator.seek(ctx.player_id, target_seconds, seek_executor)


async def _execute_seek_internal(
    ctx: CommandContext,
    player: Any,
    target_seconds: float,
) -> None:
    """
    Internal seek execution logic.

    This is called by the SeekCoordinator after coalescing and
    generation checks. It performs the actual seek work:
    1. Cancel current stream
    2. Stop and flush player
    3. Queue new stream with seek position
    4. Start playback from new position

    This function should NOT be called directly - use perform_seek() instead.
    """
    if ctx.playlist_manager is None or ctx.streaming_server is None:
        return

    # ---------------------------------------------------------------------
    # Race protection: seeking is a manual user action.
    #
    # If the protocol layer scheduled a deferred "track finished" (e.g. STMd
    # deferral because output buffer is still playing), that task MUST NOT be
    # allowed to fire after a seek, otherwise it can incorrectly advance the
    # playlist to track +1.
    #
    # We therefore:
    # 1) cancel any pending deferred track-finished task for this player (best-effort)
    # 2) suppress track-finished handling briefly (best-effort)
    # ---------------------------------------------------------------------
    try:
        slimproto = getattr(ctx, "slimproto", None)
        if slimproto is not None:
            cancel_fn = getattr(slimproto, "cancel_deferred_track_finished", None)
            if callable(cancel_fn):
                cancel_fn(ctx.player_id)

            # Suppress track-finished handling for a short window
            server = getattr(slimproto, "_resonance_server", None)
            if server is not None:
                suppress_fn = getattr(server, "suppress_track_finished_for_player", None)
                if callable(suppress_fn):
                    suppress_fn(ctx.player_id, seconds=2.0)
    except Exception:
        # Defensive: seek must still work even if suppression hooks are unavailable
        pass

    playlist = ctx.playlist_manager.get(ctx.player_id)
    if playlist is None:
        return

    current_track = playlist.current_track
    if current_track is None:
        return

    file_path = Path(current_track.path)
    suffix = file_path.suffix.lower()

    # Stop and flush player
    await player.stop()
    if hasattr(player, "flush"):
        await player.flush()

    if suffix in TRANSCODE_SEEK_FORMATS:
        # Time-based seeking for transcoded formats
        # Calculate end time (or None for no limit)
        duration = None
        if current_track.duration_ms:
            duration = current_track.duration_ms / 1000.0

        ctx.streaming_server.queue_file_with_seek(
            ctx.player_id,
            file_path,
            start_seconds=target_seconds,
            end_seconds=duration,
        )
    else:
        # Byte offset seeking for direct-stream formats
        duration_ms = current_track.duration_ms
        byte_offset = calculate_byte_offset(
            file_path=file_path,
            target_seconds=target_seconds,
            duration_ms=duration_ms,
        )

        # Byte-offset seeking: pass start_seconds for LMS-style elapsed calculation.
        # After seek, elapsed = start_seconds + raw_elapsed (same as time-based seeks).
        ctx.streaming_server.queue_file_with_byte_offset(
            ctx.player_id,
            file_path,
            byte_offset=byte_offset,
            start_seconds=target_seconds,
        )

    # Get server IP for player
    server_ip = ctx.server_host
    if ctx.slimproto is not None and hasattr(ctx.slimproto, "get_advertise_ip_for_player"):
        server_ip = ctx.slimproto.get_advertise_ip_for_player(player)

    # Start streaming from new position
    await player.start_track(
        current_track,
        server_port=ctx.server_port,
        server_ip=server_ip,
    )


def calculate_byte_offset(
    file_path: Path,
    target_seconds: float,
    duration_ms: int | None = None,
) -> int:
    """
    Calculate the byte offset for seeking in a direct-stream file.

    Uses heuristics based on file format and size:
    1. For MP3: Skip ID3v2 tag if present, then linear interpolation
    2. For FLAC/OGG/WAV: Linear interpolation based on file size and duration

    Args:
        file_path: Path to the audio file
        target_seconds: Target position in seconds
        duration_ms: Known duration in milliseconds (if available)

    Returns:
        Byte offset to seek to
    """
    if target_seconds <= 0:
        return 0

    try:
        file_size = file_path.stat().st_size
    except OSError:
        return 0

    suffix = file_path.suffix.lower().lstrip(".")

    # Calculate audio data start (skip headers/tags)
    audio_start = 0
    if suffix == "mp3":
        audio_start = _get_mp3_audio_start(file_path)

    # Calculate bytes per second
    if duration_ms and duration_ms > 0:
        duration_seconds = duration_ms / 1000.0
        audio_size = file_size - audio_start
        bytes_per_second = audio_size / duration_seconds
    else:
        # Fallback to format-specific estimate
        bytes_per_second = FORMAT_BYTES_PER_SECOND.get(suffix, 24000)

    # Calculate offset
    byte_offset = audio_start + int(target_seconds * bytes_per_second)

    # Clamp to valid range (leave some margin at end)
    min_margin = 8192  # 8KB margin
    byte_offset = max(audio_start, min(byte_offset, file_size - min_margin))

    return byte_offset


def _get_mp3_audio_start(file_path: Path) -> int:
    """
    Find the start of audio data in an MP3 file by skipping ID3v2 tags.

    ID3v2 tags are at the start of the file and have a specific header:
    - 3 bytes: "ID3"
    - 2 bytes: version
    - 1 byte: flags
    - 4 bytes: synchsafe size

    Returns:
        Byte offset where audio data starts
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(10)

            if len(header) < 10:
                return 0

            # Check for ID3v2 header
            if header[:3] != b"ID3":
                return 0

            # Parse synchsafe size (4 bytes, 7 bits each)
            size_bytes = header[6:10]
            tag_size = (
                ((size_bytes[0] & 0x7F) << 21)
                | ((size_bytes[1] & 0x7F) << 14)
                | ((size_bytes[2] & 0x7F) << 7)
                | (size_bytes[3] & 0x7F)
            )

            # ID3v2 header is 10 bytes + tag data
            return 10 + tag_size

    except OSError:
        return 0
