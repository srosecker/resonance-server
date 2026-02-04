"""
Artwork Routes for Resonance.

Provides endpoints for serving album artwork:
- /api/artwork/track/{track_id}: Get artwork for a specific track
- /api/artwork/album/{album_id}: Get artwork for a specific album
- /api/artwork/track/{track_id}/blurhash: Get BlurHash placeholder for a track
- /api/artwork/album/{album_id}/blurhash: Get BlurHash placeholder for an album
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request, Response

from resonance.web.jsonrpc_helpers import to_dict

if TYPE_CHECKING:
    from resonance.core.artwork import ArtworkManager
    from resonance.core.library import MusicLibrary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["artwork"])

# References set during route registration
_artwork_manager: ArtworkManager | None = None
_music_library: MusicLibrary | None = None


def register_artwork_routes(
    app,
    artwork_manager: ArtworkManager,
    music_library: MusicLibrary,
) -> None:
    """
    Register artwork routes with the FastAPI app.

    Args:
        app: FastAPI application instance
        artwork_manager: ArtworkManager for extracting/caching artwork
        music_library: MusicLibrary for track lookups
    """
    global _artwork_manager, _music_library
    _artwork_manager = artwork_manager
    _music_library = music_library
    app.include_router(router)


@router.get("/api/artwork/track/{track_id}")
async def get_track_artwork(
    track_id: int,
    request: Request,
) -> Response:
    """
    Serve artwork for a specific track ID.

    This endpoint fetches the track metadata to get the file path,
    then uses the ArtworkManager to extract and return the image.

    Supports HTTP caching via ETag/If-None-Match headers.
    """
    if _artwork_manager is None or _music_library is None:
        raise HTTPException(status_code=503, detail="Artwork service not initialized")

    # Get track path from database
    db = _music_library._db
    row = await db.get_track_by_id(track_id)

    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    track_path = (
        getattr(row, "path", None)
        if hasattr(row, "path")
        else row.get("path")
        if isinstance(row, dict)
        else None
    )

    if not track_path:
        raise HTTPException(status_code=404, detail="Track has no path")

    file_path = Path(track_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Track file not found")

    # Get artwork from manager (extracts or returns cached)
    try:
        result = await _artwork_manager.get_artwork(str(file_path))
        if result is None:
            raise HTTPException(status_code=404, detail="No artwork available")
        artwork_data, content_type, _etag = result
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to get artwork for track %d: %s", track_id, e)
        raise HTTPException(status_code=404, detail="No artwork available")

    # Generate ETag for caching
    etag = hashlib.md5(artwork_data).hexdigest()

    # Check If-None-Match header
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match.strip('"') == etag:
        return Response(status_code=304)

    return Response(
        content=artwork_data,
        media_type=content_type or "image/jpeg",
        headers={
            "ETag": f'"{etag}"',
            "Cache-Control": "public, max-age=86400",  # Cache for 1 day
        },
    )


@router.get("/api/artwork/album/{album_id}")
async def get_album_artwork(
    album_id: int,
    request: Request,
) -> Response:
    """
    Serve artwork for a specific album ID.

    Gets the first track from the album and extracts its artwork.
    """
    if _artwork_manager is None or _music_library is None:
        raise HTTPException(status_code=503, detail="Artwork service not initialized")

    # Get first track from album
    db = _music_library._db
    rows = await db.list_tracks_by_album(album_id=album_id, offset=0, limit=1)

    if not rows:
        raise HTTPException(status_code=404, detail="Album not found or empty")

    row = rows[0]
    track_path = (
        getattr(row, "path", None)
        if hasattr(row, "path")
        else row.get("path")
        if isinstance(row, dict)
        else None
    )

    if not track_path:
        raise HTTPException(status_code=404, detail="Album track has no path")

    file_path = Path(track_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Track file not found")

    # Get artwork from manager
    try:
        result = await _artwork_manager.get_artwork(str(file_path))
        if result is None:
            raise HTTPException(status_code=404, detail="No artwork available")
        artwork_data, content_type, _etag = result
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Failed to get artwork for album %d: %s", album_id, e)
        raise HTTPException(status_code=404, detail="No artwork available")

    # Generate ETag for caching
    etag = hashlib.md5(artwork_data).hexdigest()

    # Check If-None-Match header
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match.strip('"') == etag:
        return Response(status_code=304)

    return Response(
        content=artwork_data,
        media_type=content_type or "image/jpeg",
        headers={
            "ETag": f'"{etag}"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/artwork/{album_id}")
async def get_artwork_legacy(
    album_id: int,
    request: Request,
) -> Response:
    """
    Legacy artwork endpoint for LMS compatibility.

    Redirects to /api/artwork/album/{album_id}.
    """
    return await get_album_artwork(album_id, request)


@router.get("/music/{track_id}/cover.jpg")
async def get_music_cover_legacy(
    track_id: int,
    request: Request,
) -> Response:
    """
    Legacy cover endpoint for LMS compatibility.

    The path /music/{id}/cover.jpg is used by some LMS clients.
    """
    return await get_track_artwork(track_id, request)


@router.get("/api/artwork/track/{track_id}/blurhash")
async def get_track_blurhash(track_id: int) -> dict[str, Any]:
    """
    Get BlurHash placeholder for a track's artwork.

    BlurHash is a compact string (20-30 characters) that can be decoded
    client-side to display a blurred placeholder while the full image loads.

    Returns:
        JSON with blurhash string or null if not available.
    """
    if _artwork_manager is None or _music_library is None:
        raise HTTPException(status_code=503, detail="Artwork service not initialized")

    # Get track path from database
    db = _music_library._db
    row = await db.get_track_by_id(track_id)

    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    row_dict = to_dict(row)
    track_path = row_dict.get("path")

    if not track_path:
        return {"blurhash": None, "track_id": track_id}

    file_path = Path(track_path)
    if not file_path.exists():
        return {"blurhash": None, "track_id": track_id}

    # Get BlurHash from manager
    try:
        blurhash_str = await _artwork_manager.get_blurhash(str(file_path))
    except Exception as e:
        logger.debug("Failed to get BlurHash for track %d: %s", track_id, e)
        blurhash_str = None

    return {
        "blurhash": blurhash_str,
        "track_id": track_id,
    }


@router.get("/api/artwork/album/{album_id}/blurhash")
async def get_album_blurhash(album_id: int) -> dict[str, Any]:
    """
    Get BlurHash placeholder for an album's artwork.

    Uses the first track from the album to generate the BlurHash.

    Returns:
        JSON with blurhash string or null if not available.
    """
    if _artwork_manager is None or _music_library is None:
        raise HTTPException(status_code=503, detail="Artwork service not initialized")

    # Get first track from album
    db = _music_library._db
    rows = await db.list_tracks_by_album(album_id=album_id, offset=0, limit=1)

    if not rows:
        return {"blurhash": None, "album_id": album_id}

    row = rows[0]
    row_dict = to_dict(row)
    track_path = row_dict.get("path")

    if not track_path:
        return {"blurhash": None, "album_id": album_id}

    file_path = Path(track_path)
    if not file_path.exists():
        return {"blurhash": None, "album_id": album_id}

    # Get BlurHash from manager
    try:
        blurhash_str = await _artwork_manager.get_blurhash(str(file_path))
    except Exception as e:
        logger.debug("Failed to get BlurHash for album %d: %s", album_id, e)
        blurhash_str = None

    return {
        "blurhash": blurhash_str,
        "album_id": album_id,
    }


@router.get("/api/artwork/test")
async def test_artwork_status() -> dict[str, Any]:
    """Debug endpoint to check if ArtworkManager is alive."""
    if _artwork_manager is None:
        return {"status": "not_initialized", "available": False}

    cache_dir = _artwork_manager.cache_dir if hasattr(_artwork_manager, "cache_dir") else None
    blurhash_available = (
        _artwork_manager._blurhash_available
        if hasattr(_artwork_manager, "_blurhash_available")
        else False
    )

    return {
        "status": "ok",
        "available": True,
        "cache_dir": str(cache_dir) if cache_dir else None,
        "blurhash_available": blurhash_available,
    }
