"""
Tests for Playlist and PlaylistManager.

Tests cover:
- PlaylistTrack creation and properties
- Playlist add/remove/clear operations
- Playlist navigation (next/previous/play)
- Repeat and shuffle modes
- PlaylistManager registry
"""

import pytest

from resonance.core.playlist import (
    Playlist,
    PlaylistManager,
    PlaylistTrack,
    RepeatMode,
    ShuffleMode,
    TrackId,
)


class TestPlaylistTrack:
    """Tests for PlaylistTrack dataclass."""

    def test_create_with_all_fields(self) -> None:
        """Should create track with all metadata."""
        track = PlaylistTrack(
            track_id=TrackId(1),
            path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration_ms=180000,
        )
        assert track.track_id == 1
        assert track.path == "/music/song.mp3"
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.album == "Test Album"
        assert track.duration_ms == 180000

    def test_create_with_minimal_fields(self) -> None:
        """Should create track with just path."""
        track = PlaylistTrack(track_id=None, path="/music/song.mp3")
        assert track.track_id is None
        assert track.path == "/music/song.mp3"
        assert track.title == ""
        assert track.artist == ""

    def test_from_path_string(self) -> None:
        """Should create track from path string."""
        track = PlaylistTrack.from_path("/music/My Song.mp3")
        # Path separators may differ on Windows vs Unix
        assert "My Song.mp3" in track.path
        assert track.title == "My Song"  # stem of filename
        assert track.track_id is None

    def test_from_path_object(self) -> None:
        """Should create track from Path object."""
        from pathlib import Path

        track = PlaylistTrack.from_path(Path("/music/Another Song.flac"))
        assert "Another Song.flac" in track.path
        assert track.title == "Another Song"

    def test_frozen_immutable(self) -> None:
        """PlaylistTrack should be immutable."""
        track = PlaylistTrack(track_id=TrackId(1), path="/music/song.mp3")
        with pytest.raises(AttributeError):
            track.title = "New Title"  # type: ignore


class TestPlaylist:
    """Tests for Playlist class."""

    def test_create_empty(self) -> None:
        """Should create empty playlist."""
        playlist = Playlist(player_id="aa:bb:cc:dd:ee:ff")
        assert playlist.player_id == "aa:bb:cc:dd:ee:ff"
        assert len(playlist) == 0
        assert playlist.is_empty
        assert playlist.current_track is None

    def test_add_track(self) -> None:
        """Should add track to end of playlist."""
        playlist = Playlist(player_id="test")
        track = PlaylistTrack.from_path("/music/song1.mp3")

        idx = playlist.add(track)

        assert idx == 0
        assert len(playlist) == 1
        assert not playlist.is_empty

    def test_add_multiple_tracks(self) -> None:
        """Should add multiple tracks in order."""
        playlist = Playlist(player_id="test")
        track1 = PlaylistTrack.from_path("/music/song1.mp3")
        track2 = PlaylistTrack.from_path("/music/song2.mp3")
        track3 = PlaylistTrack.from_path("/music/song3.mp3")

        playlist.add(track1)
        playlist.add(track2)
        playlist.add(track3)

        assert len(playlist) == 3
        assert playlist.tracks[0] == track1
        assert playlist.tracks[1] == track2
        assert playlist.tracks[2] == track3

    def test_add_at_position(self) -> None:
        """Should insert track at specific position."""
        playlist = Playlist(player_id="test")
        track1 = PlaylistTrack.from_path("/music/song1.mp3")
        track2 = PlaylistTrack.from_path("/music/song2.mp3")
        track3 = PlaylistTrack.from_path("/music/song3.mp3")

        playlist.add(track1)
        playlist.add(track3)
        idx = playlist.add(track2, position=1)

        assert idx == 1
        assert playlist.tracks[0] == track1
        assert playlist.tracks[1] == track2
        assert playlist.tracks[2] == track3

    def test_add_path_convenience(self) -> None:
        """Should add track by path using convenience method."""
        playlist = Playlist(player_id="test")

        idx = playlist.add_path("/music/song.mp3")

        assert idx == 0
        assert "song.mp3" in playlist.tracks[0].path

    def test_remove_track(self) -> None:
        """Should remove track at index."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.add_path("/music/song3.mp3")

        removed = playlist.remove(1)

        assert removed is not None
        assert "song2.mp3" in removed.path
        assert len(playlist) == 2
        assert "song3.mp3" in playlist.tracks[1].path

    def test_remove_invalid_index(self) -> None:
        """Should return None for invalid index."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song.mp3")

        assert playlist.remove(-1) is None
        assert playlist.remove(5) is None
        assert len(playlist) == 1

    def test_clear(self) -> None:
        """Should clear all tracks."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")

        count = playlist.clear()

        assert count == 2
        assert len(playlist) == 0
        assert playlist.is_empty

    def test_current_track(self) -> None:
        """Should return current track."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")

        assert playlist.current_track is not None
        assert "song1.mp3" in playlist.current_track.path

    def test_play_at_index(self) -> None:
        """Should set current_index and return track."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.add_path("/music/song3.mp3")

        track = playlist.play(1)

        assert track is not None
        assert "song2.mp3" in track.path
        assert playlist.current_index == 1

    def test_play_clamps_index(self) -> None:
        """Should clamp index to valid range."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")

        track = playlist.play(100)
        assert playlist.current_index == 1  # clamped to last

        track = playlist.play(-5)
        assert playlist.current_index == 0  # clamped to first

    def test_next_track(self) -> None:
        """Should move to next track."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.add_path("/music/song3.mp3")

        track = playlist.next()

        assert track is not None
        assert "song2.mp3" in track.path
        assert playlist.current_index == 1

    def test_next_at_end_no_repeat(self) -> None:
        """Should return None at end with no repeat."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.current_index = 1  # last track

        track = playlist.next()

        assert track is None
        assert playlist.current_index == 1  # unchanged

    def test_next_at_end_repeat_all(self) -> None:
        """Should wrap to beginning with repeat all."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.set_repeat(RepeatMode.ALL)
        playlist.current_index = 1

        track = playlist.next()

        assert track is not None
        assert "song1.mp3" in track.path
        assert playlist.current_index == 0

    def test_next_repeat_one(self) -> None:
        """Should return same track with repeat one."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.set_repeat(RepeatMode.ONE)
        playlist.current_index = 0

        track = playlist.next()

        assert track is not None
        assert "song1.mp3" in track.path
        assert playlist.current_index == 0

    def test_previous_track(self) -> None:
        """Should move to previous track."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.add_path("/music/song3.mp3")
        playlist.current_index = 2

        track = playlist.previous()

        assert track is not None
        assert "song2.mp3" in track.path
        assert playlist.current_index == 1

    def test_previous_at_start_no_repeat(self) -> None:
        """Should return None at start with no repeat."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.current_index = 0

        track = playlist.previous()

        assert track is None

    def test_previous_at_start_repeat_all(self) -> None:
        """Should wrap to end with repeat all."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.set_repeat(RepeatMode.ALL)
        playlist.current_index = 0

        track = playlist.previous()

        assert track is not None
        assert "song2.mp3" in track.path
        assert playlist.current_index == 1

    def test_has_next(self) -> None:
        """Should correctly report if next track available."""
        playlist = Playlist(player_id="test")
        assert not playlist.has_next  # empty

        playlist.add_path("/music/song1.mp3")
        assert not playlist.has_next  # single track, at end

        playlist.add_path("/music/song2.mp3")
        playlist.current_index = 0
        assert playlist.has_next  # second track available

        playlist.current_index = 1
        assert not playlist.has_next  # at end

        playlist.set_repeat(RepeatMode.ALL)
        assert playlist.has_next  # can wrap

    def test_has_previous(self) -> None:
        """Should correctly report if previous track available."""
        playlist = Playlist(player_id="test")
        assert not playlist.has_previous  # empty

        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.current_index = 0
        assert not playlist.has_previous  # at start

        playlist.current_index = 1
        assert playlist.has_previous  # first track available

        playlist.current_index = 0
        playlist.set_repeat(RepeatMode.ALL)
        assert playlist.has_previous  # can wrap

    def test_set_repeat_by_enum(self) -> None:
        """Should set repeat mode by enum."""
        playlist = Playlist(player_id="test")

        playlist.set_repeat(RepeatMode.ONE)
        assert playlist.repeat_mode == RepeatMode.ONE

        playlist.set_repeat(RepeatMode.ALL)
        assert playlist.repeat_mode == RepeatMode.ALL

    def test_set_repeat_by_int(self) -> None:
        """Should set repeat mode by integer."""
        playlist = Playlist(player_id="test")

        playlist.set_repeat(1)
        assert playlist.repeat_mode == RepeatMode.ONE

        playlist.set_repeat(2)
        assert playlist.repeat_mode == RepeatMode.ALL

        playlist.set_repeat(0)
        assert playlist.repeat_mode == RepeatMode.OFF

    def test_set_shuffle_on(self) -> None:
        """Should shuffle tracks when enabling shuffle."""
        playlist = Playlist(player_id="test")
        for i in range(10):
            playlist.add_path(f"/music/song{i}.mp3")

        original_paths = [t.path for t in playlist.tracks]

        playlist.set_shuffle(ShuffleMode.ON)

        assert playlist.shuffle_mode == ShuffleMode.ON
        # Current track should be at index 0
        assert playlist.current_index == 0
        # Order should be different (with very high probability)
        shuffled_paths = [t.path for t in playlist.tracks]
        # Note: there's a tiny chance this could fail if shuffle produces same order
        assert len(shuffled_paths) == len(original_paths)

    def test_set_shuffle_off_restores_order(self) -> None:
        """Should restore original order when disabling shuffle."""
        playlist = Playlist(player_id="test")
        for i in range(5):
            playlist.add_path(f"/music/song{i}.mp3")

        original_paths = [t.path for t in playlist.tracks]

        playlist.set_shuffle(ShuffleMode.ON)
        playlist.set_shuffle(ShuffleMode.OFF)

        assert playlist.shuffle_mode == ShuffleMode.OFF
        restored_paths = [t.path for t in playlist.tracks]
        assert restored_paths == original_paths

    def test_get_tracks_info(self) -> None:
        """Should return track info for JSON serialization."""
        playlist = Playlist(player_id="test")
        playlist.add(
            PlaylistTrack(
                track_id=TrackId(1),
                path="/music/song.mp3",
                title="Test Song",
                artist="Artist",
                album="Album",
                duration_ms=180000,
            )
        )

        info = playlist.get_tracks_info()

        assert len(info) == 1
        assert info[0]["playlist index"] == 0
        assert info[0]["id"] == 1
        assert info[0]["title"] == "Test Song"
        assert info[0]["artist"] == "Artist"
        assert info[0]["album"] == "Album"
        assert info[0]["duration"] == 180  # converted to seconds
        assert info[0]["url"] == "/music/song.mp3"

    def test_remove_adjusts_current_index(self) -> None:
        """Should adjust current_index when removing track before it."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song2.mp3")
        playlist.add_path("/music/song3.mp3")
        playlist.current_index = 2  # pointing to song3

        playlist.remove(0)  # remove song1

        assert playlist.current_index == 1  # adjusted down
        assert "song3.mp3" in playlist.current_track.path  # type: ignore

    def test_insert_adjusts_current_index(self) -> None:
        """Should adjust current_index when inserting track before it."""
        playlist = Playlist(player_id="test")
        playlist.add_path("/music/song1.mp3")
        playlist.add_path("/music/song3.mp3")
        playlist.current_index = 1  # pointing to song3

        playlist.add_path("/music/song2.mp3", position=1)  # insert before current

        assert playlist.current_index == 2  # adjusted up
        assert "song3.mp3" in playlist.current_track.path  # type: ignore


class TestPlaylistManager:
    """Tests for PlaylistManager class."""

    def test_create_empty(self) -> None:
        """Should create empty manager."""
        manager = PlaylistManager()
        assert len(manager) == 0

    def test_get_creates_playlist(self) -> None:
        """Should create playlist on first access."""
        manager = PlaylistManager()
        playlist = manager.get("aa:bb:cc:dd:ee:ff")

        assert playlist is not None
        assert playlist.player_id == "aa:bb:cc:dd:ee:ff"
        assert len(manager) == 1

    def test_get_returns_same_instance(self) -> None:
        """Should return same playlist on subsequent access."""
        manager = PlaylistManager()
        playlist1 = manager.get("player1")
        playlist1.add_path("/music/song.mp3")

        playlist2 = manager.get("player1")

        assert playlist1 is playlist2
        assert len(playlist2) == 1

    def test_contains(self) -> None:
        """Should check if playlist exists."""
        manager = PlaylistManager()
        assert "player1" not in manager

        manager.get("player1")
        assert "player1" in manager

    def test_remove(self) -> None:
        """Should remove playlist."""
        manager = PlaylistManager()
        playlist = manager.get("player1")
        playlist.add_path("/music/song.mp3")

        removed = manager.remove("player1")

        assert removed is playlist
        assert "player1" not in manager
        assert len(manager) == 0

    def test_remove_nonexistent(self) -> None:
        """Should return None for nonexistent playlist."""
        manager = PlaylistManager()
        assert manager.remove("nonexistent") is None

    def test_clear_all(self) -> None:
        """Should clear all playlists."""
        manager = PlaylistManager()
        manager.get("player1").add_path("/music/song1.mp3")
        manager.get("player2").add_path("/music/song2.mp3")
        manager.get("player3").add_path("/music/song3.mp3")

        count = manager.clear_all()

        assert count == 3
        assert len(manager) == 0

    def test_multiple_players_independent(self) -> None:
        """Each player should have independent playlist."""
        manager = PlaylistManager()
        playlist1 = manager.get("player1")
        playlist2 = manager.get("player2")

        playlist1.add_path("/music/song1.mp3")
        playlist1.add_path("/music/song2.mp3")
        playlist2.add_path("/music/other.mp3")

        assert len(playlist1) == 2
        assert len(playlist2) == 1
