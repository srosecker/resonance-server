"""
Jive Menu Handler for Squeezebox Controller/Touch/Boom/Radio.

These devices use a special JSON-RPC "menu" query to build their
touch-screen UI. This module provides an implementation that allows
these devices to connect and display menus for browsing music.

Reference: Slim::Control::Jive and Slim::Menu::BrowseLibrary in the LMS codebase.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from resonance.web.handlers import CommandContext

logger = logging.getLogger(__name__)

# Constants matching LMS
BROWSELIBRARY = "browselibrary"


async def cmd_menustatus(ctx: CommandContext, command: list[Any]) -> dict[str, Any]:
    """
    Handle the 'menustatus' query for Jive devices.

    This is a notification mechanism for dynamic menu updates.
    Jive devices subscribe to this to receive menu changes.

    For now, we return an empty response since we don't have
    dynamic menu plugins that need to push updates.

    LMS command: [player_id] menustatus

    Returns:
        Empty dict (no pending menu updates)
    """
    logger.debug("menustatus query (stub): %s", command)
    return {}


async def cmd_menu(ctx: CommandContext, command: list[Any]) -> dict[str, Any]:
    """
    Handle the 'menu' query for Jive devices.

    This returns the main menu structure that Squeezebox Controller,
    Touch, Boom, and Radio devices need to build their UI.

    LMS command: [player_id] menu <start> <itemsPerResponse>

    Args:
        ctx: Command context
        command: ['menu', start_index, items_per_response, ...]

    Returns:
        Menu structure with item_loop
    """
    # Parse pagination parameters
    start = 0
    items_per_page = 100

    if len(command) > 1:
        try:
            start = int(command[1])
        except (ValueError, TypeError):
            pass

    if len(command) > 2:
        try:
            items_per_page = int(command[2])
        except (ValueError, TypeError):
            pass

    # Check for 'direct' parameter (used by disconnected players)
    direct = False
    for arg in command[3:]:
        if isinstance(arg, str) and arg == "direct:1":
            direct = True
            break

    logger.debug("menu query: start=%d, items=%d, direct=%s", start, items_per_page, direct)

    # Build the main menu structure (flat, as LMS does)
    menu_items = _build_main_menu(ctx)

    # Apply pagination
    total_count = len(menu_items)
    paginated_items = menu_items[start : start + items_per_page]

    return {
        "count": total_count,
        "offset": start,
        "item_loop": paginated_items,
    }


def _build_main_menu(ctx: CommandContext) -> list[dict[str, Any]]:
    """
    Build the main menu structure for Jive devices.

    This returns a flat list of menu items, including nodes and their children.
    The device uses 'node' to build the hierarchy and 'weight' for ordering.

    Reference: Slim::Control::Jive::mainMenu()
    """
    menu: list[dict[str, Any]] = []

    # ========================================
    # My Music node - main music browsing entry
    # ========================================
    menu.append(
        {
            "text": "My Music",
            "id": "myMusic",
            "node": "home",
            "weight": 11,
            "isANode": 1,
        }
    )

    # ========================================
    # My Music children (from BrowseLibrary)
    # ========================================

    # Artists
    menu.append(
        {
            "text": "Artists",
            "id": "myMusicArtists",
            "node": "myMusic",
            "weight": 10,
            "actions": {
                "go": {
                    "cmd": [BROWSELIBRARY, "items"],
                    "params": {
                        "menu": 1,
                        "mode": "artists",
                    },
                },
            },
        }
    )

    # Albums
    menu.append(
        {
            "text": "Albums",
            "id": "myMusicAlbums",
            "node": "myMusic",
            "weight": 20,
            "actions": {
                "go": {
                    "cmd": [BROWSELIBRARY, "items"],
                    "params": {
                        "menu": 1,
                        "mode": "albums",
                    },
                },
            },
        }
    )

    # Genres
    menu.append(
        {
            "text": "Genres",
            "id": "myMusicGenres",
            "node": "myMusic",
            "weight": 30,
            "actions": {
                "go": {
                    "cmd": [BROWSELIBRARY, "items"],
                    "params": {
                        "menu": 1,
                        "mode": "genres",
                    },
                },
            },
        }
    )

    # Years
    menu.append(
        {
            "text": "Years",
            "id": "myMusicYears",
            "node": "myMusic",
            "weight": 40,
            "actions": {
                "go": {
                    "cmd": [BROWSELIBRARY, "items"],
                    "params": {
                        "menu": 1,
                        "mode": "years",
                    },
                },
            },
        }
    )

    # New Music
    menu.append(
        {
            "text": "New Music",
            "id": "myMusicNewMusic",
            "node": "myMusic",
            "weight": 50,
            "actions": {
                "go": {
                    "cmd": [BROWSELIBRARY, "items"],
                    "params": {
                        "menu": 1,
                        "mode": "albums",
                        "sort": "new",
                    },
                },
            },
        }
    )

    # Search
    menu.append(
        {
            "text": "Search",
            "id": "myMusicSearch",
            "node": "myMusic",
            "weight": 90,
            "input": {
                "len": 1,
                "processingPopup": {
                    "text": "Searching...",
                },
                "help": {
                    "text": "Enter search text",
                },
            },
            "actions": {
                "go": {
                    "cmd": [BROWSELIBRARY, "items"],
                    "params": {
                        "menu": 1,
                        "mode": "search",
                    },
                    "itemsParams": "params",
                },
            },
            "window": {
                "isContextMenu": 1,
            },
        }
    )

    # ========================================
    # Player Power (like LMS playerPower)
    # ========================================
    menu.append(
        {
            "text": "Turn Player Off",
            "id": "playerpower",
            "node": "home",
            "weight": 100,
            "actions": {
                "do": {
                    "player": 0,
                    "cmd": ["power", "0"],
                },
            },
        }
    )

    # ========================================
    # Settings node
    # ========================================
    menu.append(
        {
            "text": "Settings",
            "id": "settings",
            "node": "home",
            "weight": 1005,
            "isANode": 1,
        }
    )

    # ========================================
    # Player Settings children
    # ========================================

    # Repeat setting
    menu.append(
        {
            "text": "Repeat",
            "id": "settingsRepeat",
            "node": "settings",
            "weight": 10,
            "choiceStrings": ["Off", "Song", "Playlist"],
            "actions": {
                "do": {
                    "player": 0,
                    "cmd": ["playlist", "repeat"],
                    "params": {"valtag": "value"},
                },
            },
        }
    )

    # Shuffle setting
    menu.append(
        {
            "text": "Shuffle",
            "id": "settingsShuffle",
            "node": "settings",
            "weight": 20,
            "choiceStrings": ["Off", "Songs", "Albums"],
            "actions": {
                "do": {
                    "player": 0,
                    "cmd": ["playlist", "shuffle"],
                    "params": {"valtag": "value"},
                },
            },
        }
    )

    # Sleep setting
    menu.append(
        {
            "text": "Sleep",
            "id": "settingsSleep",
            "node": "settings",
            "weight": 65,
            "actions": {
                "go": {
                    "cmd": ["sleepsettings"],
                    "player": 0,
                },
            },
        }
    )

    # Audio Settings node
    menu.append(
        {
            "text": "Audio Settings",
            "id": "settingsAudio",
            "node": "settings",
            "weight": 35,
            "isANode": 1,
        }
    )

    # Advanced Settings node
    menu.append(
        {
            "text": "Advanced Settings",
            "id": "advancedSettings",
            "node": "settings",
            "weight": 105,
            "isANode": 1,
        }
    )

    # Player Information
    menu.append(
        {
            "text": "Player Information",
            "id": "settingsInformation",
            "node": "advancedSettings",
            "weight": 100,
            "actions": {
                "go": {
                    "cmd": ["playerinfo"],
                    "player": 0,
                },
            },
        }
    )

    return menu


async def cmd_browselibrary(ctx: CommandContext, command: list[Any]) -> dict[str, Any]:
    """
    Handle the 'browselibrary' command for Jive menu navigation.

    This is the entry point for browsing the music library from Jive menus.

    LMS command: [player_id] browselibrary items <start> <itemsPerResponse> <params...>

    Args:
        ctx: Command context
        command: ['browselibrary', 'items', start, count, ...]

    Returns:
        Library items in Jive menu format
    """
    # Parse subcommand
    if len(command) < 2:
        return {"count": 0, "item_loop": []}

    subcmd = str(command[1]).lower()

    if subcmd != "items":
        logger.warning("Unknown browselibrary subcommand: %s", subcmd)
        return {"count": 0, "item_loop": []}

    # Parse pagination
    start = 0
    items_per_page = 100

    if len(command) > 2:
        try:
            start = int(command[2])
        except (ValueError, TypeError):
            pass

    if len(command) > 3:
        try:
            items_per_page = int(command[3])
        except (ValueError, TypeError):
            pass

    # Parse parameters
    params: dict[str, Any] = {}
    for arg in command[4:]:
        if isinstance(arg, str) and ":" in arg:
            key, value = arg.split(":", 1)
            params[key] = value
        elif isinstance(arg, dict):
            params.update(arg)

    mode = params.get("mode", "")
    logger.debug("browselibrary: mode=%s, start=%d, items=%d", mode, start, items_per_page)

    # Route to appropriate handler based on mode
    if mode == "artists":
        return await _browse_artists(ctx, start, items_per_page, params)
    elif mode == "albums":
        return await _browse_albums(ctx, start, items_per_page, params)
    elif mode == "genres":
        return await _browse_genres(ctx, start, items_per_page, params)
    elif mode == "years":
        return await _browse_years(ctx, start, items_per_page, params)
    elif mode == "tracks":
        return await _browse_tracks(ctx, start, items_per_page, params)
    elif mode == "search":
        return await _browse_search(ctx, start, items_per_page, params)
    else:
        logger.warning("Unknown browselibrary mode: %s", mode)
        return {"count": 0, "item_loop": []}


async def _browse_artists(
    ctx: CommandContext, start: int, count: int, params: dict[str, Any]
) -> dict[str, Any]:
    """Browse artists in Jive menu format."""
    # Use the existing artists handler but format for Jive
    from resonance.web.handlers.library import cmd_artists

    # Build command for existing handler
    cmd = ["artists", start, count]
    result = await cmd_artists(ctx, cmd)

    # Convert to Jive menu format
    items = []
    for artist in result.get("artists_loop", []):
        artist_id = artist.get("id", "")
        artist_name = artist.get("artist", "Unknown Artist")

        items.append(
            {
                "text": artist_name,
                "id": f"artist_{artist_id}",
                "actions": {
                    "go": {
                        "cmd": [BROWSELIBRARY, "items"],
                        "params": {
                            "menu": 1,
                            "mode": "albums",
                            "artist_id": artist_id,
                        },
                    },
                    "play": {
                        "player": 0,
                        "cmd": ["playlistcontrol"],
                        "params": {
                            "cmd": "load",
                            "artist_id": artist_id,
                        },
                    },
                    "add": {
                        "player": 0,
                        "cmd": ["playlistcontrol"],
                        "params": {
                            "cmd": "add",
                            "artist_id": artist_id,
                        },
                    },
                },
            }
        )

    return {
        "count": result.get("count", len(items)),
        "offset": start,
        "item_loop": items,
    }


async def _browse_albums(
    ctx: CommandContext, start: int, count: int, params: dict[str, Any]
) -> dict[str, Any]:
    """Browse albums in Jive menu format."""
    from resonance.web.handlers.library import cmd_albums

    # Build command for existing handler
    cmd: list[Any] = ["albums", start, count]

    # Add filters
    if params.get("artist_id"):
        cmd.append(f"artist_id:{params['artist_id']}")
    if params.get("genre_id"):
        cmd.append(f"genre_id:{params['genre_id']}")
    if params.get("year"):
        cmd.append(f"year:{params['year']}")
    if params.get("sort"):
        cmd.append(f"sort:{params['sort']}")

    # Always request artwork
    cmd.append("tags:aljJ")

    result = await cmd_albums(ctx, cmd)

    # Convert to Jive menu format
    items = []
    for album in result.get("albums_loop", []):
        album_id = album.get("id", "")
        album_title = album.get("album", "Unknown Album")
        artist_name = album.get("artist", "")

        item: dict[str, Any] = {
            "text": album_title,
            "id": f"album_{album_id}",
            "actions": {
                "go": {
                    "cmd": [BROWSELIBRARY, "items"],
                    "params": {
                        "menu": 1,
                        "mode": "tracks",
                        "album_id": album_id,
                    },
                },
                "play": {
                    "player": 0,
                    "cmd": ["playlistcontrol"],
                    "params": {
                        "cmd": "load",
                        "album_id": album_id,
                    },
                },
                "add": {
                    "player": 0,
                    "cmd": ["playlistcontrol"],
                    "params": {
                        "cmd": "add",
                        "album_id": album_id,
                    },
                },
            },
        }

        # Add artist as second line
        if artist_name:
            item["textkey"] = album_title[0].upper() if album_title else "?"
            item["icon-id"] = album.get("artwork_track_id") or album_id

        # Add artwork URL if available
        artwork_url = album.get("artwork_url")
        if artwork_url:
            item["icon"] = artwork_url
        elif album_id:
            item["icon-id"] = f"/music/{album_id}/cover"

        items.append(item)

    return {
        "count": result.get("count", len(items)),
        "offset": start,
        "item_loop": items,
    }


async def _browse_genres(
    ctx: CommandContext, start: int, count: int, params: dict[str, Any]
) -> dict[str, Any]:
    """Browse genres in Jive menu format."""
    from resonance.web.handlers.library import cmd_genres

    cmd = ["genres", start, count]
    result = await cmd_genres(ctx, cmd)

    items = []
    for genre in result.get("genres_loop", []):
        genre_id = genre.get("id", "")
        genre_name = genre.get("genre", "Unknown Genre")

        items.append(
            {
                "text": genre_name,
                "id": f"genre_{genre_id}",
                "actions": {
                    "go": {
                        "cmd": [BROWSELIBRARY, "items"],
                        "params": {
                            "menu": 1,
                            "mode": "albums",
                            "genre_id": genre_id,
                        },
                    },
                    "play": {
                        "player": 0,
                        "cmd": ["playlistcontrol"],
                        "params": {
                            "cmd": "load",
                            "genre_id": genre_id,
                        },
                    },
                },
            }
        )

    return {
        "count": result.get("count", len(items)),
        "offset": start,
        "item_loop": items,
    }


async def _browse_years(
    ctx: CommandContext, start: int, count: int, params: dict[str, Any]
) -> dict[str, Any]:
    """Browse years in Jive menu format."""
    # Get unique years from the library
    years = await ctx.music_library.get_years()

    # Sort descending (newest first)
    years = sorted(years, reverse=True)

    total = len(years)
    paginated = years[start : start + count]

    items = []
    for year in paginated:
        year_str = str(year) if year else "Unknown"
        items.append(
            {
                "text": year_str,
                "id": f"year_{year}",
                "actions": {
                    "go": {
                        "cmd": [BROWSELIBRARY, "items"],
                        "params": {
                            "menu": 1,
                            "mode": "albums",
                            "year": year,
                        },
                    },
                    "play": {
                        "player": 0,
                        "cmd": ["playlistcontrol"],
                        "params": {
                            "cmd": "load",
                            "year": year,
                        },
                    },
                },
            }
        )

    return {
        "count": total,
        "offset": start,
        "item_loop": items,
    }


async def _browse_tracks(
    ctx: CommandContext, start: int, count: int, params: dict[str, Any]
) -> dict[str, Any]:
    """Browse tracks in Jive menu format."""
    from resonance.web.handlers.library import cmd_titles

    cmd: list[Any] = ["titles", start, count]

    # Add filters
    if params.get("album_id"):
        cmd.append(f"album_id:{params['album_id']}")
    if params.get("artist_id"):
        cmd.append(f"artist_id:{params['artist_id']}")
    if params.get("genre_id"):
        cmd.append(f"genre_id:{params['genre_id']}")

    # Request useful tags
    cmd.append("tags:aAdtl")

    result = await cmd_titles(ctx, cmd)

    items = []
    for track in result.get("titles_loop", []):
        track_id = track.get("id", "")
        track_title = track.get("title", "Unknown Track")
        artist_name = track.get("artist", "")
        duration = track.get("duration", 0)

        # Format duration
        if duration:
            mins = int(duration) // 60
            secs = int(duration) % 60
            duration_str = f"{mins}:{secs:02d}"
        else:
            duration_str = ""

        item: dict[str, Any] = {
            "text": track_title,
            "id": f"track_{track_id}",
            "type": "audio",
            "playAction": "play",
            "goAction": "play",
            "nextWindow": "nowPlaying",
            "actions": {
                "go": {
                    "player": 0,
                    "cmd": ["playlistcontrol"],
                    "params": {
                        "cmd": "load",
                        "track_id": track_id,
                    },
                    "nextWindow": "nowPlaying",
                },
                "play": {
                    "player": 0,
                    "cmd": ["playlistcontrol"],
                    "params": {
                        "cmd": "load",
                        "track_id": track_id,
                    },
                    "nextWindow": "nowPlaying",
                },
                "add": {
                    "player": 0,
                    "cmd": ["playlistcontrol"],
                    "params": {
                        "cmd": "add",
                        "track_id": track_id,
                    },
                },
                "add-hold": {
                    "player": 0,
                    "cmd": ["playlistcontrol"],
                    "params": {
                        "cmd": "insert",
                        "track_id": track_id,
                    },
                },
            },
        }

        # Add artist as second line if available
        if artist_name:
            item["textkey"] = track_title[0].upper() if track_title else "?"

        items.append(item)

    return {
        "count": result.get("count", len(items)),
        "offset": start,
        "item_loop": items,
    }


async def _browse_search(
    ctx: CommandContext, start: int, count: int, params: dict[str, Any]
) -> dict[str, Any]:
    """Handle search in Jive menu format."""
    search_term = params.get("search", "")

    if not search_term:
        # Return search input prompt
        return {
            "count": 1,
            "offset": 0,
            "item_loop": [
                {
                    "text": "Enter search term",
                    "style": "itemNoAction",
                    "type": "text",
                }
            ],
        }

    from resonance.web.handlers.library import cmd_search

    cmd = ["search", 0, count, f"term:{search_term}"]
    result = await cmd_search(ctx, cmd)

    items = []

    # Add artists found
    for artist in result.get("artists_loop", [])[:5]:
        artist_id = artist.get("id", "")
        artist_name = artist.get("artist", "")
        items.append(
            {
                "text": artist_name,
                "id": f"search_artist_{artist_id}",
                "textkey": "A",
                "actions": {
                    "go": {
                        "cmd": [BROWSELIBRARY, "items"],
                        "params": {"menu": 1, "mode": "albums", "artist_id": artist_id},
                    },
                },
            }
        )

    # Add albums found
    for album in result.get("albums_loop", [])[:5]:
        album_id = album.get("id", "")
        album_title = album.get("album", "")
        items.append(
            {
                "text": album_title,
                "id": f"search_album_{album_id}",
                "textkey": "B",
                "icon-id": f"/music/{album_id}/cover",
                "actions": {
                    "go": {
                        "cmd": [BROWSELIBRARY, "items"],
                        "params": {"menu": 1, "mode": "tracks", "album_id": album_id},
                    },
                    "play": {
                        "player": 0,
                        "cmd": ["playlistcontrol"],
                        "params": {"cmd": "load", "album_id": album_id},
                    },
                },
            }
        )

    # Add tracks found
    for track in result.get("titles_loop", [])[:10]:
        track_id = track.get("id", "")
        track_title = track.get("title", "")
        items.append(
            {
                "text": track_title,
                "id": f"search_track_{track_id}",
                "textkey": "C",
                "type": "audio",
                "actions": {
                    "play": {
                        "player": 0,
                        "cmd": ["playlistcontrol"],
                        "params": {"cmd": "load", "track_id": track_id},
                    },
                    "add": {
                        "player": 0,
                        "cmd": ["playlistcontrol"],
                        "params": {"cmd": "add", "track_id": track_id},
                    },
                },
            }
        )

    return {
        "count": len(items),
        "offset": 0,
        "item_loop": items,
    }


async def cmd_date(ctx: CommandContext, command: list[Any]) -> dict[str, Any]:
    """
    Handle the 'date' query for Jive devices.

    Returns the current date/time for clock display.

    Args:
        ctx: Command context
        command: ['date', ...]

    Returns:
        Date/time information
    """
    now = time.time()
    local_time = time.localtime(now)

    return {
        "date_epoch": int(now),
        "date": time.strftime("%Y-%m-%d", local_time),
        "time": int(now),
        "timezone": time.strftime("%Z", local_time),
        "timezone_offset": -time.timezone if time.daylight == 0 else -time.altzone,
    }


async def cmd_alarm_settings(
    ctx: CommandContext, command: list[Any]
) -> dict[str, Any]:
    """
    Handle the 'alarmsettings' query for Jive devices.

    Returns alarm configuration (stub - alarms not yet implemented).
    """
    return {
        "count": 0,
        "offset": 0,
        "item_loop": [],
    }


async def cmd_sleep_settings(
    ctx: CommandContext, command: list[Any]
) -> dict[str, Any]:
    """
    Handle the 'sleepsettings' query for Jive devices.

    Returns sleep timer options.
    """
    sleep_options = [
        {
            "text": "Off",
            "radio": 1,
            "actions": {"do": {"player": 0, "cmd": ["sleep", "0"]}},
            "nextWindow": "parent",
        },
        {
            "text": "15 minutes",
            "radio": 0,
            "actions": {"do": {"player": 0, "cmd": ["sleep", "900"]}},
            "nextWindow": "parent",
        },
        {
            "text": "30 minutes",
            "radio": 0,
            "actions": {"do": {"player": 0, "cmd": ["sleep", "1800"]}},
            "nextWindow": "parent",
        },
        {
            "text": "45 minutes",
            "radio": 0,
            "actions": {"do": {"player": 0, "cmd": ["sleep", "2700"]}},
            "nextWindow": "parent",
        },
        {
            "text": "1 hour",
            "radio": 0,
            "actions": {"do": {"player": 0, "cmd": ["sleep", "3600"]}},
            "nextWindow": "parent",
        },
        {
            "text": "2 hours",
            "radio": 0,
            "actions": {"do": {"player": 0, "cmd": ["sleep", "7200"]}},
            "nextWindow": "parent",
        },
    ]

    return {
        "count": len(sleep_options),
        "offset": 0,
        "item_loop": sleep_options,
    }


async def cmd_sync_settings(
    ctx: CommandContext, command: list[Any]
) -> dict[str, Any]:
    """
    Handle the 'syncsettings' query for Jive devices.

    Returns sync group settings (stub - sync not yet fully implemented).
    """
    return {
        "count": 1,
        "offset": 0,
        "item_loop": [
            {
                "text": "Not synced",
                "style": "item_no_arrow",
            }
        ],
    }


async def cmd_firmwareupgrade(
    ctx: CommandContext, command: list[Any]
) -> dict[str, Any]:
    """
    Handle the 'firmwareupgrade' query for Jive devices.

    Tells the device there's no firmware upgrade available.

    LMS returns:
    - firmwareUpgrade: 0 (no upgrade needed) or 1 (upgrade required)
    - relativeFirmwareUrl or firmwareUrl: URL to firmware file (if upgrade available)
    """
    return {
        "firmwareUpgrade": 0,
    }


async def cmd_playlistcontrol(
    ctx: CommandContext, command: list[Any]
) -> dict[str, Any]:
    """
    Handle the 'playlistcontrol' command for Jive menu actions.

    This is used by Jive menus to add/play tracks, albums, artists, etc.

    LMS command: [player_id] playlistcontrol cmd:<cmd> <param>:<value>
    """
    # Parse parameters
    params: dict[str, Any] = {}
    for arg in command[1:]:
        if isinstance(arg, str) and ":" in arg:
            key, value = arg.split(":", 1)
            params[key] = value

    cmd_action = params.get("cmd", "load")

    logger.debug("playlistcontrol: cmd=%s, params=%s", cmd_action, params)

    # Route to existing playlist handler
    # Build equivalent playlist command
    if params.get("track_id"):
        track_id = params["track_id"]
        if cmd_action == "load":
            playlist_cmd = ["playlist", "loadtracks", f"track_id:{track_id}"]
        elif cmd_action == "add":
            playlist_cmd = ["playlist", "addtracks", f"track_id:{track_id}"]
        elif cmd_action == "insert":
            playlist_cmd = ["playlist", "inserttracks", f"track_id:{track_id}"]
        else:
            return {}
    elif params.get("album_id"):
        album_id = params["album_id"]
        if cmd_action == "load":
            playlist_cmd = ["playlist", "loadtracks", f"album_id:{album_id}"]
        elif cmd_action == "add":
            playlist_cmd = ["playlist", "addtracks", f"album_id:{album_id}"]
        else:
            return {}
    elif params.get("artist_id"):
        artist_id = params["artist_id"]
        if cmd_action == "load":
            playlist_cmd = ["playlist", "loadtracks", f"artist_id:{artist_id}"]
        elif cmd_action == "add":
            playlist_cmd = ["playlist", "addtracks", f"artist_id:{artist_id}"]
        else:
            return {}
    elif params.get("genre_id"):
        genre_id = params["genre_id"]
        if cmd_action == "load":
            playlist_cmd = ["playlist", "loadtracks", f"genre_id:{genre_id}"]
        elif cmd_action == "add":
            playlist_cmd = ["playlist", "addtracks", f"genre_id:{genre_id}"]
        else:
            return {}
    elif params.get("year"):
        year = params["year"]
        if cmd_action == "load":
            playlist_cmd = ["playlist", "loadtracks", f"year:{year}"]
        elif cmd_action == "add":
            playlist_cmd = ["playlist", "addtracks", f"year:{year}"]
        else:
            return {}
    else:
        logger.warning("playlistcontrol: no recognized parameters")
        return {}

    # Execute via playlist handler
    from resonance.web.handlers.playlist import cmd_playlist

    return await cmd_playlist(ctx, playlist_cmd)


async def cmd_playerinfo(ctx: CommandContext, command: list[Any]) -> dict[str, Any]:
    """
    Handle the 'playerinfo' command for Jive devices.

    Returns player information for the settings menu.
    """
    player = ctx.player_registry.get(ctx.player_id)

    if not player:
        return {
            "count": 1,
            "offset": 0,
            "item_loop": [{"text": "Player not found", "style": "item_no_arrow"}],
        }

    items = [
        {"text": f"Name: {player.name}", "style": "item_no_arrow"},
        {"text": f"Model: {player.info.model}", "style": "item_no_arrow"},
        {"text": f"MAC: {player.info.mac_address}", "style": "item_no_arrow"},
        {"text": f"Firmware: {player.info.firmware_version}", "style": "item_no_arrow"},
        {"text": f"Server: Resonance", "style": "item_no_arrow"},
    ]

    return {
        "count": len(items),
        "offset": 0,
        "item_loop": items,
    }
