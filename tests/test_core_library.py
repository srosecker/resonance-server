"""
Tests for resonance.core.library and related modules.

These tests verify:
- LibraryDb schema creation and CRUD operations
- Scanner metadata extraction
- MusicLibrary facade operations
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from resonance.core.library import (
    Album,
    Artist,
    MusicLibrary,
    MusicLibraryError,
    MusicLibraryNotReadyError,
    ScanResult,
    Track,
)
from resonance.core.library_db import LibraryDb, TrackRow, UpsertTrack
from resonance.core.scanner import (
    ScanConfig,
    TrackMetadata,
    _extract_metadata,
    _first_text,
    _parse_int_maybe,
    _parse_year_maybe,
    scan_music_folder,
)

# =============================================================================
# LibraryDb Tests
# =============================================================================


class TestLibraryDb:
    """Tests for the database layer."""

    @pytest.fixture
    async def db(self) -> LibraryDb:
        """Create an in-memory database for testing."""
        db = LibraryDb(":memory:")
        await db.open()
        await db.ensure_schema()
        yield db
        await db.close()

    async def test_open_close(self) -> None:
        """Test basic open/close lifecycle."""
        db = LibraryDb(":memory:")
        assert not db.is_open

        await db.open()
        assert db.is_open

        await db.close()
        assert not db.is_open

    async def test_ensure_schema_creates_tables(self, db: LibraryDb) -> None:
        """Test that ensure_schema creates the tracks table."""
        # If we got here without error, schema was created
        count = await db.count_tracks()
        assert count == 0

    async def test_upsert_track_insert(self, db: LibraryDb) -> None:
        """Test inserting a new track."""
        track = UpsertTrack(
            path="/music/test.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            year=2024,
            duration_ms=180000,
            track_no=1,
        )

        track_id = await db.upsert_track(track)
        assert track_id > 0

        # Verify it was inserted
        row = await db.get_track_by_id(track_id)
        assert row is not None
        assert row.path == "/music/test.mp3"
        assert row.title == "Test Song"
        assert row.artist == "Test Artist"
        assert row.album == "Test Album"
        assert row.year == 2024
        assert row.duration_ms == 180000

    async def test_upsert_track_update(self, db: LibraryDb) -> None:
        """Test updating an existing track by path."""
        # Insert initial
        track1 = UpsertTrack(
            path="/music/test.mp3",
            title="Original Title",
            artist="Original Artist",
        )
        id1 = await db.upsert_track(track1)

        # Update with same path
        track2 = UpsertTrack(
            path="/music/test.mp3",
            title="Updated Title",
            artist="Updated Artist",
        )
        id2 = await db.upsert_track(track2)

        # Should be same ID (upsert, not insert)
        assert id1 == id2

        # Verify updated
        row = await db.get_track_by_id(id1)
        assert row is not None
        assert row.title == "Updated Title"
        assert row.artist == "Updated Artist"

    async def test_upsert_tracks_bulk(self, db: LibraryDb) -> None:
        """Test bulk upsert."""
        tracks = [UpsertTrack(path=f"/music/song{i}.mp3", title=f"Song {i}") for i in range(10)]

        count = await db.upsert_tracks(tracks)
        assert count == 10

        total = await db.count_tracks()
        assert total == 10

    async def test_get_track_by_path(self, db: LibraryDb) -> None:
        """Test lookup by path."""
        await db.upsert_track(UpsertTrack(path="/music/findme.mp3", title="Find Me"))

        row = await db.get_track_by_path("/music/findme.mp3")
        assert row is not None
        assert row.title == "Find Me"

        # Non-existent path
        row = await db.get_track_by_path("/music/notfound.mp3")
        assert row is None

    async def test_list_tracks_ordering(self, db: LibraryDb) -> None:
        """Test that list_tracks respects ordering."""
        await db.upsert_tracks(
            [
                UpsertTrack(path="/b.mp3", title="B Song", artist="Zebra"),
                UpsertTrack(path="/a.mp3", title="A Song", artist="Alpha"),
                UpsertTrack(path="/c.mp3", title="C Song", artist="Beta"),
            ]
        )

        # Order by artist
        rows = await db.list_tracks(order_by="artist")
        assert len(rows) == 3
        assert rows[0].artist == "Alpha"
        assert rows[1].artist == "Beta"
        assert rows[2].artist == "Zebra"

    async def test_list_tracks_pagination(self, db: LibraryDb) -> None:
        """Test pagination in list_tracks."""
        await db.upsert_tracks(
            [UpsertTrack(path=f"/song{i:02d}.mp3", title=f"Song {i}") for i in range(20)]
        )

        page1 = await db.list_tracks(limit=5, offset=0, order_by="path")
        page2 = await db.list_tracks(limit=5, offset=5, order_by="path")

        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].path != page2[0].path

    async def test_list_artists(self, db: LibraryDb) -> None:
        """Test listing unique artists."""
        await db.upsert_tracks(
            [
                UpsertTrack(path="/1.mp3", artist="Artist A"),
                UpsertTrack(path="/2.mp3", artist="Artist B"),
                UpsertTrack(path="/3.mp3", artist="Artist A"),  # Duplicate
                UpsertTrack(path="/4.mp3", artist="Artist C"),
            ]
        )

        artists = await db.list_artists()
        assert len(artists) == 3
        assert "Artist A" in artists
        assert "Artist B" in artists
        assert "Artist C" in artists

    async def test_list_albums(self, db: LibraryDb) -> None:
        """Test listing unique albums."""
        await db.upsert_tracks(
            [
                UpsertTrack(path="/1.mp3", album="Album X"),
                UpsertTrack(path="/2.mp3", album="Album Y"),
                UpsertTrack(path="/3.mp3", album="Album X"),  # Duplicate
            ]
        )

        albums = await db.list_albums()
        assert len(albums) == 2
        assert "Album X" in albums
        assert "Album Y" in albums

    async def test_search_tracks(self, db: LibraryDb) -> None:
        """Test search functionality."""
        await db.upsert_tracks(
            [
                UpsertTrack(path="/1.mp3", title="Hello World", artist="John"),
                UpsertTrack(path="/2.mp3", title="Goodbye", artist="Jane"),
                UpsertTrack(path="/3.mp3", title="Testing", artist="Hello"),
            ]
        )

        # Search in title
        results = await db.search_tracks("Hello")
        assert len(results) == 2  # "Hello World" title + "Hello" artist

        # Search in artist
        results = await db.search_tracks("Jane")
        assert len(results) == 1
        assert results[0].artist == "Jane"

    async def test_delete_track_by_path(self, db: LibraryDb) -> None:
        """Test deleting a track."""
        await db.upsert_track(UpsertTrack(path="/delete_me.mp3", title="Delete Me"))

        deleted = await db.delete_track_by_path("/delete_me.mp3")
        assert deleted is True

        # Verify gone
        row = await db.get_track_by_path("/delete_me.mp3")
        assert row is None

        # Delete non-existent
        deleted = await db.delete_track_by_path("/not_there.mp3")
        assert deleted is False

    async def test_normalize_text_strips_whitespace(self, db: LibraryDb) -> None:
        """Test that text fields are normalized."""
        await db.upsert_track(
            UpsertTrack(
                path="/test.mp3",
                title="  Spaces Around  ",
                artist="",  # Empty string should become NULL
            )
        )

        row = await db.get_track_by_path("/test.mp3")
        assert row is not None
        assert row.title == "Spaces Around"
        assert row.artist is None  # Empty string normalized to NULL


# =============================================================================
# Scanner Helper Tests
# =============================================================================


class TestScannerHelpers:
    """Tests for scanner utility functions."""

    def test_first_text_string(self) -> None:
        assert _first_text("hello") == "hello"
        assert _first_text("  spaced  ") == "spaced"
        assert _first_text("") is None

    def test_first_text_list(self) -> None:
        assert _first_text(["first", "second"]) == "first"
        assert _first_text([]) is None

    def test_first_text_none(self) -> None:
        assert _first_text(None) is None

    def test_parse_int_maybe_simple(self) -> None:
        assert _parse_int_maybe("5") == 5
        assert _parse_int_maybe("42") == 42

    def test_parse_int_maybe_with_total(self) -> None:
        assert _parse_int_maybe("3/12") == 3
        assert _parse_int_maybe("1/1") == 1

    def test_parse_int_maybe_invalid(self) -> None:
        assert _parse_int_maybe("abc") is None
        assert _parse_int_maybe("") is None
        assert _parse_int_maybe(None) is None

    def test_parse_year_maybe_simple(self) -> None:
        assert _parse_year_maybe("2024") == 2024
        assert _parse_year_maybe("1999") == 1999

    def test_parse_year_maybe_date_format(self) -> None:
        assert _parse_year_maybe("2024-01-15") == 2024
        assert _parse_year_maybe("1985-12-31") == 1985

    def test_parse_year_maybe_invalid(self) -> None:
        assert _parse_year_maybe("abc") is None
        assert _parse_year_maybe("") is None
        assert _parse_year_maybe(None) is None


# =============================================================================
# MusicLibrary Facade Tests
# =============================================================================


class TestMusicLibrary:
    """Tests for the high-level MusicLibrary facade."""

    @pytest.fixture
    async def library(self) -> MusicLibrary:
        """Create a MusicLibrary with in-memory DB."""
        db = LibraryDb(":memory:")
        await db.open()
        await db.ensure_schema()

        lib = MusicLibrary(db=db, music_root=None)
        await lib.initialize()

        yield lib

        await db.close()

    async def test_not_initialized_raises(self) -> None:
        """Test that operations fail before initialization."""
        db = LibraryDb(":memory:")
        lib = MusicLibrary(db=db)

        with pytest.raises(MusicLibraryNotReadyError):
            await lib.get_artists()

        await db.close()

    async def test_initialize_requires_open_db(self) -> None:
        """Test that initialize fails if DB is not open."""
        db = LibraryDb(":memory:")
        lib = MusicLibrary(db=db)

        with pytest.raises(MusicLibraryError):
            await lib.initialize()

    async def test_get_artists_empty(self, library: MusicLibrary) -> None:
        """Test get_artists on empty library."""
        artists = await library.get_artists()
        assert artists == ()

    async def test_get_albums_empty(self, library: MusicLibrary) -> None:
        """Test get_albums on empty library."""
        albums = await library.get_albums()
        assert albums == ()

    async def test_get_tracks_empty(self, library: MusicLibrary) -> None:
        """Test get_tracks on empty library."""
        tracks = await library.get_tracks()
        assert tracks == ()

    async def test_search_empty_query(self, library: MusicLibrary) -> None:
        """Test that empty search returns empty result."""
        result = await library.search("")
        assert result.tracks == ()
        assert result.artists == ()
        assert result.albums == ()

    async def test_search_whitespace_query(self, library: MusicLibrary) -> None:
        """Test that whitespace-only search returns empty result."""
        result = await library.search("   ")
        assert result.tracks == ()

    async def test_get_track_by_id_not_found(self, library: MusicLibrary) -> None:
        """Test get_track_by_id returns None for missing track."""
        track = await library.get_track_by_id(99999)
        assert track is None

    async def test_get_track_by_path_not_found(self, library: MusicLibrary) -> None:
        """Test get_track_by_path returns None for missing track."""
        track = await library.get_track_by_path("/not/found.mp3")
        assert track is None

    async def test_paging_validation(self, library: MusicLibrary) -> None:
        """Test that invalid paging parameters raise errors."""
        with pytest.raises(ValueError):
            await library.get_artists(offset=-1)

        with pytest.raises(ValueError):
            await library.get_artists(limit=0)

        with pytest.raises(ValueError):
            await library.get_artists(limit=100000)

    async def test_scan_no_roots_raises(self, library: MusicLibrary) -> None:
        """Test that scan fails without roots configured."""
        # library was created with music_root=None
        with pytest.raises(MusicLibraryError, match="No scan roots"):
            await library.scan()


# =============================================================================
# Integration Test: Scan + Query
# =============================================================================


class TestLibraryIntegration:
    """Integration tests that verify the full scan → query flow."""

    @pytest.fixture
    async def library_with_db(self):
        """Create a MusicLibrary with in-memory DB for integration tests."""
        db = LibraryDb(":memory:")
        await db.open()
        await db.ensure_schema()

        lib = MusicLibrary(db=db, music_root=None)
        await lib.initialize()

        yield lib, db

        await db.close()

    async def test_manual_track_insert_and_query(self, library_with_db) -> None:
        """Test inserting tracks via DB and querying via facade."""
        lib, db = library_with_db

        # Insert some tracks directly via DB
        await db.upsert_tracks(
            [
                UpsertTrack(
                    path="/music/artist1/album1/song1.mp3",
                    title="Song One",
                    artist="Artist One",
                    album="Album One",
                    year=2020,
                    track_no=1,
                    duration_ms=200000,
                ),
                UpsertTrack(
                    path="/music/artist1/album1/song2.mp3",
                    title="Song Two",
                    artist="Artist One",
                    album="Album One",
                    year=2020,
                    track_no=2,
                    duration_ms=180000,
                ),
                UpsertTrack(
                    path="/music/artist2/album2/song1.mp3",
                    title="Different Song",
                    artist="Artist Two",
                    album="Album Two",
                    year=2021,
                    track_no=1,
                    duration_ms=240000,
                ),
            ]
        )
        await db.commit()

        # Query via facade
        artists = await lib.get_artists()
        assert len(artists) == 2

        albums = await lib.get_albums()
        assert len(albums) == 2

        tracks = await lib.get_tracks()
        assert len(tracks) == 3

        # Search
        result = await lib.search("Artist One")
        assert len(result.tracks) == 2

        result = await lib.search("Different")
        assert len(result.tracks) == 1
        assert result.tracks[0].title == "Different Song"

    async def test_get_track_by_path_returns_track(self, library_with_db) -> None:
        """Test that get_track_by_path returns proper Track object."""
        lib, db = library_with_db

        await db.upsert_track(
            UpsertTrack(
                path="/test/path.mp3",
                title="Test Title",
                artist="Test Artist",
                album="Test Album",
                year=2023,
                track_no=5,
                disc_no=1,
                duration_ms=300000,
            )
        )
        await db.commit()

        track = await lib.get_track_by_path("/test/path.mp3")

        assert track is not None
        assert isinstance(track, Track)
        assert track.path == "/test/path.mp3"
        assert track.title == "Test Title"
        assert track.artist_name == "Test Artist"
        assert track.album_title == "Test Album"
        assert track.year == 2023
        assert track.track_no == 5
        assert track.disc_no == 1
        assert track.duration_ms == 300000
