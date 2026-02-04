"""
JSON-RPC Helper Functions.

This module provides utilities for JSON-RPC command processing:
- Query parameter parsing (start, itemsPerResponse, tags, filters)
- Loop item building (converting DB results to LMS-format response items)
- Sort mapping (LMS sort parameters to SQL ORDER BY)
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any

logger = logging.getLogger(__name__)


def to_dict(row: Any) -> dict[str, Any]:
    """
    Convert a row (dict or dataclass) to a dictionary.

    Args:
        row: Either a dict or a dataclass instance

    Returns:
        Dictionary representation
    """
    if isinstance(row, dict):
        return row
    if is_dataclass(row) and not isinstance(row, type):
        return asdict(row)
    # Try to convert via __dict__ as fallback
    if hasattr(row, "__dict__"):
        return dict(row.__dict__)
    # Last resort: try dict()
    try:
        return dict(row)
    except (TypeError, ValueError):
        return {}


# =============================================================================
# Query Parameter Parsing
# =============================================================================


def parse_start_items(params: list[Any]) -> tuple[int, int]:
    """
    Parse start index and items per response from command params.

    LMS commands use positional params: [command, start, items, ...]

    Args:
        params: Command parameters list

    Returns:
        Tuple of (start_index, items_per_response)
    """
    start = 0
    items = 100  # Default

    if len(params) >= 2:
        try:
            start = int(params[1])
        except (ValueError, TypeError):
            pass

    if len(params) >= 3:
        try:
            items = int(params[2])
        except (ValueError, TypeError):
            pass

    return start, items


def parse_tagged_params(params: list[Any]) -> dict[str, str]:
    """
    Parse tagged parameters from command params.

    LMS uses "tag:value" format for filters and options.
    Examples: "tags:als", "year:2020", "genre_id:5", "artist_id:10"

    Args:
        params: Command parameters list

    Returns:
        Dictionary of tag -> value
    """
    result: dict[str, str] = {}

    for param in params:
        if not isinstance(param, str):
            continue
        if ":" not in param:
            continue

        # Split on first colon only
        parts = param.split(":", 1)
        if len(parts) == 2:
            tag, value = parts
            result[tag] = value

    return result


def parse_tags_string(tags_str: str) -> set[str]:
    """
    Parse a tags string into a set of single-character tags.

    LMS uses a string of characters to indicate which fields to include.
    Example: "als" means include 'a' (artist), 'l' (album), 's' (something)

    Args:
        tags_str: String of tag characters

    Returns:
        Set of single-character tags
    """
    return set(tags_str)


def get_filter_int(tagged_params: dict[str, str], key: str) -> int | None:
    """
    Get an integer filter value from tagged params.

    Args:
        tagged_params: Parsed tagged parameters
        key: The key to look up (e.g., "year", "genre_id")

    Returns:
        Integer value or None if not present/invalid
    """
    value = tagged_params.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def get_filter_str(tagged_params: dict[str, str], key: str) -> str | None:
    """
    Get a string filter value from tagged params.

    Args:
        tagged_params: Parsed tagged parameters
        key: The key to look up

    Returns:
        String value or None if not present
    """
    return tagged_params.get(key)


# =============================================================================
# Sort Mapping
# =============================================================================

# Maps LMS sort parameter values to (column, ascending) tuples
ARTIST_SORT_MAP: dict[str, tuple[str, bool]] = {
    "artist": ("name", True),
    "artistsort": ("name_sort", True),
    "id": ("id", True),
    "albums": ("album_count", False),  # Most albums first
    "tracks": ("track_count", False),  # Most tracks first
}

ALBUM_SORT_MAP: dict[str, tuple[str, bool]] = {
    "album": ("title", True),
    "albumsort": ("title_sort", True),
    "id": ("id", True),
    "year": ("year", False),  # Newest first
    "artist": ("artist_name", True),
    "artflow": ("artist_name", True),  # LMS alias
    "new": ("id", False),  # Recently added (approximated by ID)
}

TRACK_SORT_MAP: dict[str, tuple[str, bool]] = {
    "title": ("title", True),
    "titlesort": ("title_sort", True),
    "id": ("id", True),
    "album": ("album_title", True),
    "artist": ("artist_name", True),
    "year": ("year", False),
    "tracknum": ("track_no", True),
    "duration": ("duration_ms", True),
    "new": ("id", False),
}


def get_sort_params(
    tagged_params: dict[str, str],
    sort_map: dict[str, tuple[str, bool]],
    default_column: str = "name",
) -> tuple[str, bool]:
    """
    Get sort column and direction from tagged params.

    Args:
        tagged_params: Parsed tagged parameters
        sort_map: Mapping of sort names to (column, ascending)
        default_column: Default column if no sort specified

    Returns:
        Tuple of (column_name, ascending)
    """
    sort_key = tagged_params.get("sort", "").lower()

    if sort_key in sort_map:
        return sort_map[sort_key]

    return default_column, True


# =============================================================================
# Loop Item Builders
# =============================================================================

# Tag character to field name mappings for LMS compatibility
ARTIST_TAG_MAP: dict[str, str] = {
    "s": "id",  # Standard LMS uses 's' for artist
    "a": "artist",  # Artist name
    "textkey": "textkey",  # First letter for indexing
}

ALBUM_TAG_MAP: dict[str, str] = {
    "l": "album",  # Album title
    "a": "artist",  # Artist name
    "y": "year",  # Year
    "S": "artist_id",  # Artist ID
    "j": "artwork_track_id",  # Artwork reference
    "id": "id",  # Album ID
    "e": "album_id",  # LMS uses 'e' for album_id in some contexts
    "X": "album_replay_gain",  # Replay gain
}

TRACK_TAG_MAP: dict[str, str] = {
    "t": "title",  # Track title
    "a": "artist",  # Artist name
    "l": "album",  # Album name
    "y": "year",  # Year
    "d": "duration",  # Duration in seconds
    "n": "tracknum",  # Track number
    "i": "disc",  # Disc number
    "u": "url",  # Track URL for streaming
    "o": "type",  # Content type (format)
    "r": "bitrate",  # Bitrate
    "T": "samplerate",  # Sample rate
    "I": "samplesize",  # Bit depth (sample size)
    "id": "id",  # Track ID
    "s": "artist_id",  # Artist ID
    "e": "album_id",  # Album ID
    "j": "coverart",  # Cover art available
    "J": "artwork_track_id",  # Artwork track ID
    "K": "artwork_url",  # Artwork URL
    "c": "coverid",  # Cover ID
}

GENRE_TAG_MAP: dict[str, str] = {
    "id": "id",
    "genre": "genre",
}

ROLE_TAG_MAP: dict[str, str] = {
    "id": "id",
    "role": "role",
}


def build_artist_item(
    row: Any,
    tags: set[str] | None = None,
    include_all: bool = False,
) -> dict[str, Any]:
    """
    Build an artist loop item from a database row.

    Args:
        row: Database result row (dict or dataclass)
        tags: Set of tag characters to include (None = all)
        include_all: If True, include all fields regardless of tags

    Returns:
        LMS-format artist item
    """
    row_dict = to_dict(row)
    item: dict[str, Any] = {}

    # Always include id
    item["id"] = row_dict.get("id")

    # Name is always included as "artist"
    item["artist"] = row_dict.get("name", row_dict.get("artist", ""))

    if include_all or tags is None or "s" in tags:
        # 's' is the standard tag for artists
        pass  # id already included

    if include_all or tags is None:
        if row_dict.get("album_count") is not None:
            item["albums"] = row_dict["album_count"]
        if row_dict.get("track_count") is not None:
            item["track_count"] = row_dict["track_count"]

    # Generate textkey (first letter for indexing)
    name = row_dict.get("name", row_dict.get("artist", ""))
    if name:
        item["textkey"] = name[0].upper()

    return item


def build_album_item(
    row: Any,
    tags: set[str] | None = None,
    include_all: bool = False,
    server_url: str = "",
) -> dict[str, Any]:
    """
    Build an album loop item from a database row.

    Args:
        row: Database result row (dict or dataclass)
        tags: Set of tag characters to include (None = all)
        include_all: If True, include all fields regardless of tags
        server_url: Base URL for artwork

    Returns:
        LMS-format album item
    """
    row_dict = to_dict(row)
    item: dict[str, Any] = {}

    # Always include id and album title
    # DB queries return 'name' for album title in some cases, 'title' in others
    item["id"] = row_dict.get("id")
    item["album"] = row_dict.get("title", row_dict.get("name", row_dict.get("album", "")))

    if include_all or tags is None or "a" in tags:
        # DB queries return 'artist' in some dict results, 'artist_name' in others
        artist = row_dict.get("artist_name", row_dict.get("artist"))
        if artist:
            item["artist"] = artist

    if include_all or tags is None or "y" in tags:
        year = row_dict.get("year")
        if year:
            item["year"] = year

    if include_all or tags is None or "S" in tags:
        artist_id = row_dict.get("artist_id")
        if artist_id:
            item["artist_id"] = artist_id

    if include_all or tags is None:
        track_count = row_dict.get("track_count")
        if track_count is not None:
            item["tracks"] = track_count

    # Artwork
    if include_all or tags is None or "j" in tags or "J" in tags:
        album_id = row_dict.get("id")
        if album_id and server_url:
            item["artwork_track_id"] = album_id
            item["artwork_url"] = f"{server_url}/artwork/{album_id}"

    # Generate textkey
    title = row_dict.get("title", row_dict.get("album", ""))
    if title:
        item["textkey"] = title[0].upper()

    return item


def build_track_item(
    row: Any,
    tags: set[str] | None = None,
    include_all: bool = False,
    server_url: str = "",
) -> dict[str, Any]:
    """
    Build a track/title loop item from a database row.

    Args:
        row: Database result row (dict or dataclass)
        tags: Set of tag characters to include (None = all)
        include_all: If True, include all fields regardless of tags
        server_url: Base URL for streaming and artwork

    Returns:
        LMS-format track item
    """
    row_dict = to_dict(row)
    item: dict[str, Any] = {}

    # Always include id and title
    item["id"] = row_dict.get("id")
    item["title"] = row_dict.get("title", "")

    if include_all or tags is None or "a" in tags:
        artist = row_dict.get("artist_name", row_dict.get("artist"))
        if artist:
            item["artist"] = artist

    if include_all or tags is None or "l" in tags:
        album = row_dict.get("album_title", row_dict.get("album"))
        if album:
            item["album"] = album

    if include_all or tags is None or "y" in tags:
        year = row_dict.get("year")
        if year:
            item["year"] = year

    if include_all or tags is None or "d" in tags:
        duration_ms = row_dict.get("duration_ms")
        if duration_ms is not None:
            item["duration"] = duration_ms / 1000.0  # Convert to seconds

    if include_all or tags is None or "n" in tags:
        track_no = row_dict.get("track_no")
        if track_no is not None:
            item["tracknum"] = track_no

    if include_all or tags is None or "i" in tags:
        disc_no = row_dict.get("disc_no")
        if disc_no is not None:
            item["disc"] = disc_no

    if include_all or tags is None or "s" in tags:
        artist_id = row_dict.get("artist_id")
        if artist_id is not None:
            item["artist_id"] = artist_id

    if include_all or tags is None or "e" in tags:
        album_id = row_dict.get("album_id")
        if album_id is not None:
            item["album_id"] = album_id

    # URL is ALWAYS included when available (needed for playback)
    # Note: 'u' tag controls inclusion, but url is critical for playback
    path = row_dict.get("path")
    if path:
        item["url"] = path  # Use actual path for LMS compat

    # Audio quality metadata
    if include_all or tags is None or "o" in tags:
        path = row_dict.get("path", "")
        if path:
            # Determine format from file extension
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            format_map = {
                "mp3": "mp3",
                "flac": "flc",
                "ogg": "ogg",
                "m4a": "aac",
                "m4b": "aac",
                "wav": "wav",
                "aiff": "aif",
                "aif": "aif",
                "opus": "ops",
            }
            item["type"] = format_map.get(ext, ext)

    if include_all or tags is None or "r" in tags:
        bitrate = row_dict.get("bitrate")
        if bitrate:
            item["bitrate"] = bitrate

    if include_all or tags is None or "T" in tags:
        sample_rate = row_dict.get("sample_rate")
        if sample_rate:
            item["samplerate"] = sample_rate

    if include_all or tags is None or "I" in tags:
        bit_depth = row_dict.get("bit_depth")
        if bit_depth:
            item["samplesize"] = bit_depth

    # Channels
    channels = row_dict.get("channels")
    if channels:
        item["channels"] = channels

    # Artwork
    if include_all or tags is None or "j" in tags or "J" in tags or "K" in tags:
        album_id = row_dict.get("album_id")
        if album_id and server_url:
            item["coverart"] = 1
            item["artwork_track_id"] = row_dict.get("id")
            item["artwork_url"] = f"{server_url}/artwork/{album_id}"

    # Generate textkey
    title = row_dict.get("title", "")
    if title:
        item["textkey"] = title[0].upper()

    return item


def build_genre_item(
    row: Any,
    tags: set[str] | None = None,
    include_all: bool = False,
) -> dict[str, Any]:
    """
    Build a genre loop item from a database row.

    Args:
        row: Database result row (dict or dataclass)
        tags: Set of tag characters to include (None = all)
        include_all: If True, include all fields regardless of tags

    Returns:
        LMS-format genre item
    """
    row_dict = to_dict(row)
    item: dict[str, Any] = {}

    # Always include id
    item["id"] = row_dict.get("id")

    # Genre name is included unless tags gating excludes it
    # tags:i means only id, so we check if tags is set and doesn't include genre indicators
    if include_all or tags is None or "g" in tags:
        item["genre"] = row_dict.get("name", row_dict.get("genre", ""))

    if include_all or tags is None:
        track_count = row_dict.get("track_count")
        if track_count is not None:
            item["tracks"] = track_count

    return item


def build_role_item(
    row: Any,
    tags: set[str] | None = None,
    include_all: bool = False,
) -> dict[str, Any]:
    """
    Build a role loop item from a database row.

    Args:
        row: Database result row (dict or dataclass)
        tags: Set of tag characters to include (None = all)
        include_all: If True, include all fields regardless of tags

    Returns:
        LMS-format role item
    """
    row_dict = to_dict(row)
    item: dict[str, Any] = {}

    # Always include id as role_id for LMS compatibility
    item["role_id"] = row_dict.get("id")

    # Include role_name if tags include 't' (text/title) or no tags specified
    if include_all or tags is None or "t" in tags:
        item["role_name"] = row_dict.get("name", row_dict.get("role", ""))

    return item


def build_player_item(player: Any) -> dict[str, Any]:
    """
    Build a player loop item from a Player object.

    Args:
        player: Player instance with name, mac_address, etc.

    Returns:
        LMS-format player item
    """
    return {
        "playerid": player.mac_address,
        "name": player.name,
        "displaytype": getattr(player.info, "device_type", "squeezebox").name.lower()
        if hasattr(player, "info")
        else "squeezebox",
        "isplayer": 1,
        "canpoweroff": 1,
        "connected": 1,
        "model": getattr(player.info, "device_type", "squeezebox").name.lower()
        if hasattr(player, "info")
        else "squeezebox",
        "power": 1,
    }


# =============================================================================
# Response Building
# =============================================================================


def build_list_response(
    items: list[dict[str, Any]],
    total_count: int,
    loop_name: str,
) -> dict[str, Any]:
    """
    Build a standard LMS list response.

    Args:
        items: List of items for the loop
        total_count: Total count of matching items (for pagination)
        loop_name: Name of the loop field (e.g., "artists_loop")

    Returns:
        LMS-format response dict
    """
    return {
        "count": total_count,
        loop_name: items,
    }


def build_error_response(code: int, message: str) -> dict[str, Any]:
    """
    Build a JSON-RPC error response.

    Args:
        code: Error code
        message: Error message

    Returns:
        Error dict for JSON-RPC response
    """
    return {
        "code": code,
        "message": message,
    }


# Standard JSON-RPC error codes
ERROR_PARSE_ERROR = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL_ERROR = -32603
