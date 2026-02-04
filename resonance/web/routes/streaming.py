"""
Streaming Routes for Resonance.

Provides the /stream.mp3 endpoint for audio streaming to Squeezebox players.

Decision logic for transcoding vs. direct streaming is centralized in
resonance.streaming.policy to ensure consistency between the HTTP route
and the player's format expectations (strm command).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from resonance.streaming.policy import needs_transcoding
from resonance.streaming.transcoder import get_transcode_config, transcode_stream

if TYPE_CHECKING:
    from resonance.streaming.server import StreamingServer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["streaming"])

# Reference to StreamingServer, set during route registration
_streaming_server: StreamingServer | None = None


def register_streaming_routes(
    app,
    streaming_server: StreamingServer | None = None,
) -> None:
    """
    Register streaming routes with the FastAPI app.

    Args:
        app: FastAPI application instance
        streaming_server: StreamingServer for file resolution (optional, falls back to app.state)
    """
    global _streaming_server
    # Use provided streaming_server or fall back to app.state
    if streaming_server is not None:
        _streaming_server = streaming_server
    elif hasattr(app, "state") and hasattr(app.state, "streaming_server"):
        _streaming_server = app.state.streaming_server
    app.include_router(router)


@router.get("/stream.mp3")
async def stream_audio(
    request: Request,
    player: str | None = None,
) -> StreamingResponse:
    """
    Stream audio to a Squeezebox player.

    The player MAC address is passed as a query parameter.
    The streaming server resolves which file to serve based on
    the player's current playlist.

    Decision logic (shared policy):
    - Uses `resonance.streaming.policy.needs_transcoding()` as the single source of truth.

    Args:
        request: The FastAPI request.
        player: Player MAC address (query parameter).
        range: Optional Range header for seeking.

    Returns:
        StreamingResponse with audio data.

    Raises:
        HTTPException: 404 if no file is available for the player.
    """
    if _streaming_server is None:
        raise HTTPException(status_code=503, detail="Streaming server not initialized")

    if player is None:
        raise HTTPException(status_code=400, detail="Missing player parameter")

    # Resolve the file to stream
    file_path = _streaming_server.resolve_file(player)
    if file_path is None:
        raise HTTPException(status_code=404, detail="No track queued for player")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    file_size = file_path.stat().st_size
    suffix = file_path.suffix.lower()

    # Get Range header from request
    range_header = request.headers.get("range")

    # Check if we need to transcode
    if needs_transcoding(suffix, device_type=None):
        return await _stream_with_transcoding(player, file_path)
    else:
        return await _stream_direct(player, file_path, file_size, range_header)


async def _stream_with_transcoding(
    player_mac: str,
    file_path: Path,
) -> StreamingResponse:
    """
    Stream a file with transcoding (for M4B/M4A/MP4 etc.).

    Uses the transcoder module to convert to a streamable format.
    """
    if _streaming_server is None:
        raise HTTPException(status_code=503, detail="Streaming server not initialized")

    # Get file extension and find transcoding rule
    suffix = file_path.suffix.lower().lstrip(".")
    config = get_transcode_config()
    rule = config.find_rule(suffix)
    if rule is None:
        raise HTTPException(status_code=500, detail=f"No transcoding rule for format: {suffix}")

    # Check for seek position (time-based seeking for transcoded files)
    seek_pos = _streaming_server.get_seek_position(player_mac)
    start_seconds = seek_pos[0] if seek_pos else None
    end_seconds = seek_pos[1] if seek_pos else None

    # Get cancellation token for stream abort
    cancel_token = _streaming_server.get_cancellation_token(player_mac)

    async def generate() -> AsyncIterator[bytes]:
        """Generate transcoded audio chunks."""
        chunk_count = 0
        try:
            async for chunk in transcode_stream(
                file_path,
                rule=rule,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
            ):
                # Check for cancellation every 4 chunks
                if chunk_count % 4 == 0 and cancel_token and cancel_token.cancelled:
                    logger.info("Stream cancelled for player %s (transcoded)", player_mac)
                    break

                yield chunk
                chunk_count += 1

                # Clear seek position after first chunk
                if chunk_count == 1:
                    _streaming_server.clear_seek_position(player_mac)

        except Exception as e:
            logger.exception("Transcoding error for %s: %s", file_path, e)

    # Transcoded output is MP3 (as per streaming/policy.py)
    return StreamingResponse(
        generate(),
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "none",  # No byte-range seeking for transcoded streams
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _stream_direct(
    player_mac: str,
    file_path: Path,
    file_size: int,
    range_header: str | None,
) -> StreamingResponse:
    """
    Stream a file directly without transcoding (for MP3/FLAC/OGG etc.).

    Supports byte-range requests for seeking.
    """
    if _streaming_server is None:
        raise HTTPException(status_code=503, detail="Streaming server not initialized")

    content_type = _get_content_type(file_path)

    # Check for forced byte offset (from time-based seeking)
    forced_offset = _streaming_server.get_byte_offset(player_mac)

    # Parse Range header or use forced offset
    start_byte = 0
    end_byte = file_size - 1

    if forced_offset is not None:
        start_byte = min(forced_offset, file_size - 1)
    elif range_header:
        start_byte, end_byte = _parse_range_header(range_header, file_size)

    content_length = end_byte - start_byte + 1

    # Get cancellation token
    cancel_token = _streaming_server.get_cancellation_token(player_mac)

    async def generate() -> AsyncIterator[bytes]:
        """Generate file chunks from the specified byte range."""
        chunk_size = 65536  # 64KB chunks
        chunk_count = 0

        try:
            with open(file_path, "rb") as f:
                f.seek(start_byte)
                remaining = content_length

                while remaining > 0:
                    # Check for cancellation every 4 chunks
                    if chunk_count % 4 == 0 and cancel_token and cancel_token.cancelled:
                        logger.info("Stream cancelled for player %s (direct)", player_mac)
                        break

                    read_size = min(chunk_size, remaining)
                    chunk = f.read(read_size)
                    if not chunk:
                        break

                    yield chunk
                    remaining -= len(chunk)
                    chunk_count += 1

                    # Clear byte offset after first chunk
                    if chunk_count == 1 and forced_offset is not None:
                        _streaming_server.clear_byte_offset(player_mac)

        except Exception as e:
            logger.exception("Streaming error for %s: %s", file_path, e)

    # Determine response status and headers
    if start_byte > 0 or end_byte < file_size - 1:
        # Partial content
        return StreamingResponse(
            generate(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
            },
        )
    else:
        # Full content
        return StreamingResponse(
            generate(),
            media_type=content_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            },
        )


def _get_content_type(file_path: Path) -> str:
    """Get the MIME type for an audio file."""
    suffix = file_path.suffix.lower()
    content_types = {
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".wav": "audio/wav",
        ".aiff": "audio/aiff",
        ".aif": "audio/aiff",
        ".m4a": "audio/mp4",
        ".m4b": "audio/mp4",
        ".aac": "audio/aac",
    }
    return content_types.get(suffix, "application/octet-stream")


def _parse_range_header(
    range_header: str,
    file_size: int,
) -> tuple[int, int]:
    """
    Parse an HTTP Range header.

    Args:
        range_header: The Range header value (e.g., "bytes=0-1023")
        file_size: Total file size for validation

    Returns:
        Tuple of (start_byte, end_byte)
    """
    try:
        # Parse "bytes=start-end" format
        if not range_header.startswith("bytes="):
            return 0, file_size - 1

        range_spec = range_header[6:]  # Remove "bytes="

        if range_spec.startswith("-"):
            # Suffix range: "-500" means last 500 bytes
            suffix_len = int(range_spec[1:])
            start = max(0, file_size - suffix_len)
            return start, file_size - 1

        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

        # Clamp values
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))

        return start, end

    except (ValueError, IndexError):
        return 0, file_size - 1
