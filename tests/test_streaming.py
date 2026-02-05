"""
Tests for the streaming route.

Tests cover:
- Streaming endpoint availability
- Player parameter handling
- 404 when no track is available
- Content-Type headers
- Range request support (partial content)
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from resonance.streaming.server import StreamingServer
from resonance.web.routes.streaming import register_streaming_routes


@pytest.fixture
def temp_audio_file() -> Path:
    """Create a temporary audio file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        # Write some fake audio data (1KB)
        f.write(b"FAKE_MP3_DATA" * 100)
        return Path(f.name)


@pytest.fixture
def streaming_server() -> StreamingServer:
    """Create a StreamingServer instance for testing."""
    return StreamingServer()


class TestStreamingServerSeek:
    """Tests for StreamingServer seek position management."""

    def test_queue_file_with_seek_stores_position(self) -> None:
        """queue_file_with_seek stores the seek position."""
        server = StreamingServer()
        file_path = Path("/music/audiobook.m4b")
        player_mac = "aa:bb:cc:dd:ee:ff"

        server.queue_file_with_seek(player_mac, file_path, start_seconds=120.5)

        # File should be queued
        assert server.get_queued_file(player_mac) == file_path

        # Seek position should be stored
        seek_pos = server.get_seek_position(player_mac)
        assert seek_pos is not None
        assert seek_pos[0] == 120.5
        assert seek_pos[1] is None

    def test_queue_file_with_seek_stores_end_position(self) -> None:
        """queue_file_with_seek stores both start and end positions."""
        server = StreamingServer()
        file_path = Path("/music/audiobook.m4b")
        player_mac = "aa:bb:cc:dd:ee:ff"

        server.queue_file_with_seek(player_mac, file_path, start_seconds=60.0, end_seconds=180.0)

        seek_pos = server.get_seek_position(player_mac)
        assert seek_pos is not None
        assert seek_pos[0] == 60.0
        assert seek_pos[1] == 180.0

    def test_queue_file_clears_seek_position(self) -> None:
        """queue_file (without seek) clears any previous seek position."""
        server = StreamingServer()
        file_path = Path("/music/audiobook.m4b")
        player_mac = "aa:bb:cc:dd:ee:ff"

        # First queue with seek
        server.queue_file_with_seek(player_mac, file_path, start_seconds=120.0)
        assert server.get_seek_position(player_mac) is not None

        # Then queue without seek
        server.queue_file(player_mac, file_path)

        # Seek position should be cleared
        assert server.get_seek_position(player_mac) is None

    def test_clear_seek_position(self) -> None:
        """clear_seek_position removes the seek position."""
        server = StreamingServer()
        file_path = Path("/music/audiobook.m4b")
        player_mac = "aa:bb:cc:dd:ee:ff"

        server.queue_file_with_seek(player_mac, file_path, start_seconds=120.0)
        assert server.get_seek_position(player_mac) is not None

        server.clear_seek_position(player_mac)
        assert server.get_seek_position(player_mac) is None

    def test_get_seek_position_returns_none_for_unknown_player(self) -> None:
        """get_seek_position returns None for unknown player."""
        server = StreamingServer()
        assert server.get_seek_position("unknown:player:mac") is None

    def test_queue_file_with_byte_offset_stores_offset(self) -> None:
        """queue_file_with_byte_offset stores the byte offset."""
        server = StreamingServer()
        file_path = Path("/music/song.mp3")
        player_mac = "aa:bb:cc:dd:ee:ff"

        server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=1024000)

        # File should be queued
        assert server.get_queued_file(player_mac) == file_path

        # Byte offset should be stored
        byte_offset = server.get_byte_offset(player_mac)
        assert byte_offset == 1024000

    def test_queue_file_with_byte_offset_sets_start_offset(self) -> None:
        """queue_file_with_byte_offset sets start_offset for LMS-style elapsed calculation."""
        server = StreamingServer()
        file_path = Path("/music/song.mp3")
        player_mac = "aa:bb:cc:dd:ee:ff"

        # Queue with byte offset AND start_seconds for elapsed calculation
        server.queue_file_with_byte_offset(
            player_mac, file_path, byte_offset=1024000, start_seconds=60.0
        )

        # start_offset should be set (for elapsed = start_offset + raw_elapsed)
        assert server.get_start_offset(player_mac) == 60.0

    def test_queue_file_with_byte_offset_without_start_seconds(self) -> None:
        """queue_file_with_byte_offset without start_seconds clears start_offset."""
        server = StreamingServer()
        file_path = Path("/music/song.mp3")
        player_mac = "aa:bb:cc:dd:ee:ff"

        # First set a start_offset via time-based seek
        server.queue_file_with_seek(player_mac, file_path, start_seconds=120.0)
        assert server.get_start_offset(player_mac) == 120.0

        # Queue with byte offset but no start_seconds (e.g., start from beginning)
        server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=0)

        # start_offset should be cleared (0.0)
        assert server.get_start_offset(player_mac) == 0.0

    def test_queue_file_with_byte_offset_clears_seek_position(self) -> None:
        """queue_file_with_byte_offset clears any time-based seek position."""
        server = StreamingServer()
        file_path = Path("/music/song.mp3")
        player_mac = "aa:bb:cc:dd:ee:ff"

        # First queue with time-based seek
        server.queue_file_with_seek(player_mac, file_path, start_seconds=120.0)
        assert server.get_seek_position(player_mac) is not None

        # Then queue with byte offset
        server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=1024000)

        # Time-based seek should be cleared, byte offset set
        assert server.get_seek_position(player_mac) is None
        assert server.get_byte_offset(player_mac) == 1024000

    def test_queue_file_with_seek_clears_byte_offset(self) -> None:
        """queue_file_with_seek clears any byte offset."""
        server = StreamingServer()
        file_path = Path("/music/song.mp3")
        player_mac = "aa:bb:cc:dd:ee:ff"

        # First queue with byte offset
        server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=1024000)
        assert server.get_byte_offset(player_mac) is not None

        # Then queue with time-based seek
        server.queue_file_with_seek(player_mac, file_path, start_seconds=60.0)

        # Byte offset should be cleared, time-based seek set
        assert server.get_byte_offset(player_mac) is None
        assert server.get_seek_position(player_mac) is not None

    def test_clear_byte_offset(self) -> None:
        """clear_byte_offset removes the byte offset."""
        server = StreamingServer()
        file_path = Path("/music/song.mp3")
        player_mac = "aa:bb:cc:dd:ee:ff"

        server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=1024000)
        assert server.get_byte_offset(player_mac) is not None

        server.clear_byte_offset(player_mac)
        assert server.get_byte_offset(player_mac) is None

    def test_get_byte_offset_returns_none_for_unknown_player(self) -> None:
        """get_byte_offset returns None for unknown player."""
        server = StreamingServer()
        assert server.get_byte_offset("unknown:player:mac") is None

    def test_queue_file_clears_byte_offset(self) -> None:
        """queue_file (without offset) clears any previous byte offset."""
        server = StreamingServer()
        file_path = Path("/music/song.mp3")
        player_mac = "aa:bb:cc:dd:ee:ff"

        # First queue with byte offset
        server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=1024000)
        assert server.get_byte_offset(player_mac) is not None

        # Then queue without offset
        server.queue_file(player_mac, file_path)

        # Byte offset should be cleared
        assert server.get_byte_offset(player_mac) is None


class TestDirectStreamSeekingIntegration:
    """
    Integration tests for direct-stream seeking with forced byte offset.

    These tests verify the full flow:
    queue_file_with_byte_offset → /stream.mp3 → response starts at correct byte
    """

    def test_stream_with_forced_byte_offset_returns_partial_content(self) -> None:
        """Stream should return 206 with correct Content-Range when byte offset is set."""
        server = StreamingServer()

        # Create a 10KB test file with known content
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            # Write 10KB of data: first 5KB is 'A', next 5KB is 'B'
            f.write(b"A" * 5000)
            f.write(b"B" * 5000)
            file_path = Path(f.name)

        try:
            player_mac = "aa:bb:cc:dd:ee:ff"
            byte_offset = 5000  # Start at the 'B' section

            server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=byte_offset)

            # Create app and client
            app = FastAPI()
            app.state.streaming_server = server
            register_streaming_routes(app)
            client = TestClient(app)

            response = client.get(f"/stream.mp3?player={player_mac}")

            # Should return 206 Partial Content
            assert response.status_code == 206
            assert "content-range" in response.headers

            # Content-Range should indicate we started at byte 5000
            content_range = response.headers["content-range"]
            assert content_range.startswith("bytes 5000-")

            # Content should be the 'B' section (second half of file)
            assert response.content.startswith(b"B")
            assert len(response.content) == 5000
        finally:
            file_path.unlink(missing_ok=True)

    def test_stream_with_forced_byte_offset_clears_offset_after_streaming(self) -> None:
        """Byte offset should be cleared after stream starts (one-time use)."""
        server = StreamingServer()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"AUDIO_DATA" * 1000)
            file_path = Path(f.name)

        try:
            player_mac = "aa:bb:cc:dd:ee:ff"
            server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=1000)

            # Verify offset is set before streaming
            assert server.get_byte_offset(player_mac) == 1000

            # Create app and stream
            app = FastAPI()
            app.state.streaming_server = server
            register_streaming_routes(app)
            client = TestClient(app)

            response = client.get(f"/stream.mp3?player={player_mac}")
            assert response.status_code == 206

            # After streaming, byte offset should be cleared
            assert server.get_byte_offset(player_mac) is None
        finally:
            file_path.unlink(missing_ok=True)

    def test_stream_with_zero_byte_offset_returns_full_content(self) -> None:
        """Byte offset of 0 should behave like no offset (return 200, not 206)."""
        server = StreamingServer()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"FULL_AUDIO" * 100)
            file_path = Path(f.name)

        try:
            player_mac = "aa:bb:cc:dd:ee:ff"
            # Queue with byte_offset=0 (should be treated as "no offset")
            server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=0)

            app = FastAPI()
            app.state.streaming_server = server
            register_streaming_routes(app)
            client = TestClient(app)

            response = client.get(f"/stream.mp3?player={player_mac}")

            # Offset of 0 means start from beginning - should be 200 OK
            assert response.status_code == 200
            assert response.content.startswith(b"FULL_AUDIO")
        finally:
            file_path.unlink(missing_ok=True)

    def test_stream_byte_offset_clamped_to_file_size(self) -> None:
        """Byte offset larger than file size should be clamped."""
        server = StreamingServer()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"SMALL_FILE")  # 10 bytes
            file_path = Path(f.name)

        try:
            player_mac = "aa:bb:cc:dd:ee:ff"
            # Request offset way past file end
            server.queue_file_with_byte_offset(player_mac, file_path, byte_offset=999999)

            app = FastAPI()
            app.state.streaming_server = server
            register_streaming_routes(app)
            client = TestClient(app)

            response = client.get(f"/stream.mp3?player={player_mac}")

            # Should still get a response (clamped to valid range)
            assert response.status_code in (200, 206)
            # Should get at least some content (clamped near end)
            assert len(response.content) >= 1
        finally:
            file_path.unlink(missing_ok=True)


@pytest.fixture
def app(streaming_server: StreamingServer) -> FastAPI:
    """Create a FastAPI app with streaming routes."""
    app = FastAPI()
    app.state.streaming_server = streaming_server
    register_streaming_routes(app)
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestStreamingEndpoint:
    """Tests for GET /stream.mp3 endpoint."""

    def test_missing_player_parameter(self, client: TestClient) -> None:
        """Should return 400 when player parameter is missing."""
        response = client.get("/stream.mp3")
        assert response.status_code == 400
        assert "player" in response.json()["detail"].lower()

    def test_no_file_for_player(self, client: TestClient) -> None:
        """Should return 404 when no track is queued for player."""
        response = client.get("/stream.mp3?player=aa:bb:cc:dd:ee:ff")
        assert response.status_code == 404
        assert "track" in response.json()["detail"].lower()

    def test_stream_queued_file(
        self,
        client: TestClient,
        streaming_server: StreamingServer,
        temp_audio_file: Path,
    ) -> None:
        """Should stream the queued file for a player."""
        player_mac = "aa:bb:cc:dd:ee:ff"
        streaming_server.queue_file(player_mac, temp_audio_file)

        response = client.get(f"/stream.mp3?player={player_mac}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert "content-length" in response.headers
        assert len(response.content) > 0

    def test_content_type_flac(
        self,
        client: TestClient,
        streaming_server: StreamingServer,
    ) -> None:
        """Should return correct content-type for FLAC files."""
        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as f:
            f.write(b"FAKE_FLAC_DATA" * 100)
            flac_path = Path(f.name)

        player_mac = "aa:bb:cc:dd:ee:ff"
        streaming_server.queue_file(player_mac, flac_path)

        response = client.get(f"/stream.mp3?player={player_mac}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/flac"

    def test_accept_ranges_header(
        self,
        client: TestClient,
        streaming_server: StreamingServer,
        temp_audio_file: Path,
    ) -> None:
        """Should include Accept-Ranges header."""
        player_mac = "aa:bb:cc:dd:ee:ff"
        streaming_server.queue_file(player_mac, temp_audio_file)

        response = client.get(f"/stream.mp3?player={player_mac}")

        assert response.status_code == 200
        assert response.headers.get("accept-ranges") == "bytes"

    def test_range_request_partial_content(
        self,
        client: TestClient,
        streaming_server: StreamingServer,
        temp_audio_file: Path,
    ) -> None:
        """Should support Range requests for seeking."""
        player_mac = "aa:bb:cc:dd:ee:ff"
        streaming_server.queue_file(player_mac, temp_audio_file)

        # Request bytes 0-99
        response = client.get(
            f"/stream.mp3?player={player_mac}",
            headers={"Range": "bytes=0-99"},
        )

        assert response.status_code == 206  # Partial Content
        assert "content-range" in response.headers
        assert len(response.content) == 100

    def test_range_request_from_offset(
        self,
        client: TestClient,
        streaming_server: StreamingServer,
        temp_audio_file: Path,
    ) -> None:
        """Should handle Range request with start offset."""
        player_mac = "aa:bb:cc:dd:ee:ff"
        streaming_server.queue_file(player_mac, temp_audio_file)

        file_size = temp_audio_file.stat().st_size

        # Request from byte 100 to end
        response = client.get(
            f"/stream.mp3?player={player_mac}",
            headers={"Range": "bytes=100-"},
        )

        assert response.status_code == 206
        expected_length = file_size - 100
        assert len(response.content) == expected_length


class TestStreamingServer:
    """Tests for StreamingServer class."""

    def test_queue_and_get_file(self, streaming_server: StreamingServer) -> None:
        """Should queue and retrieve files."""
        player_mac = "aa:bb:cc:dd:ee:ff"
        file_path = Path("/music/song.mp3")

        streaming_server.queue_file(player_mac, file_path)

        assert streaming_server.get_queued_file(player_mac) == file_path

    def test_dequeue_file(self, streaming_server: StreamingServer) -> None:
        """Should dequeue (remove) files."""
        player_mac = "aa:bb:cc:dd:ee:ff"
        file_path = Path("/music/song.mp3")

        streaming_server.queue_file(player_mac, file_path)
        dequeued = streaming_server.dequeue_file(player_mac)

        assert dequeued == file_path
        assert streaming_server.get_queued_file(player_mac) is None

    def test_resolve_file_from_queue(self, streaming_server: StreamingServer) -> None:
        """Should resolve file from queue."""
        player_mac = "aa:bb:cc:dd:ee:ff"
        file_path = Path("/music/song.mp3")

        streaming_server.queue_file(player_mac, file_path)

        assert streaming_server.resolve_file(player_mac) == file_path

    def test_resolve_file_from_provider(self) -> None:
        """Should resolve file from audio provider callback."""
        file_path = Path("/music/provider_song.mp3")

        def provider(mac: str) -> Path | None:
            return file_path if mac == "aa:bb:cc:dd:ee:ff" else None

        server = StreamingServer(audio_provider=provider)

        assert server.resolve_file("aa:bb:cc:dd:ee:ff") == file_path
        assert server.resolve_file("other:mac:addr") is None

    def test_queue_takes_precedence_over_provider(self) -> None:
        """Queue should take precedence over audio provider."""
        queue_file = Path("/music/queued.mp3")
        provider_file = Path("/music/provider.mp3")

        def provider(mac: str) -> Path:
            return provider_file

        server = StreamingServer(audio_provider=provider)
        server.queue_file("aa:bb:cc:dd:ee:ff", queue_file)

        assert server.resolve_file("aa:bb:cc:dd:ee:ff") == queue_file

    def test_get_content_type_mp3(self) -> None:
        """Should return correct content type for MP3."""
        assert StreamingServer.get_content_type(Path("song.mp3")) == "audio/mpeg"

    def test_get_content_type_flac(self) -> None:
        """Should return correct content type for FLAC."""
        assert StreamingServer.get_content_type(Path("song.flac")) == "audio/flac"

    def test_get_content_type_ogg(self) -> None:
        """Should return correct content type for OGG."""
        assert StreamingServer.get_content_type(Path("song.ogg")) == "audio/ogg"

    def test_get_content_type_m4a(self) -> None:
        """Should return correct content type for M4A."""
        assert StreamingServer.get_content_type(Path("song.m4a")) == "audio/mp4"

    def test_get_content_type_opus(self) -> None:
        """Should return correct content type for Opus."""
        assert StreamingServer.get_content_type(Path("song.opus")) == "audio/opus"

    def test_parse_range_header_full(self) -> None:
        """Should parse full range header."""
        start, end = StreamingServer.parse_range_header("bytes=0-999", 2000)
        assert start == 0
        assert end == 999

    def test_parse_range_header_from_start(self) -> None:
        """Should parse range header with only start."""
        start, end = StreamingServer.parse_range_header("bytes=500-", 2000)
        assert start == 500
        assert end == 1999  # end of file

    def test_parse_range_header_none(self) -> None:
        """Should return full range when header is None."""
        start, end = StreamingServer.parse_range_header(None, 2000)
        assert start == 0
        assert end == 1999

    def test_parse_range_header_clamps_values(self) -> None:
        """Should clamp range values to file size."""
        start, end = StreamingServer.parse_range_header("bytes=0-10000", 1000)
        assert start == 0
        assert end == 999  # clamped to file size - 1

    async def test_start_stop(self, streaming_server: StreamingServer) -> None:
        """Should start and stop without binding a port."""
        assert not streaming_server.is_running

        await streaming_server.start()
        assert streaming_server.is_running

        await streaming_server.stop()
        assert not streaming_server.is_running

    async def test_stop_clears_queue(self, streaming_server: StreamingServer) -> None:
        """Should clear queue when stopped."""
        streaming_server.queue_file("player1", Path("/music/song1.mp3"))
        streaming_server.queue_file("player2", Path("/music/song2.mp3"))

        await streaming_server.start()
        await streaming_server.stop()

        assert streaming_server.get_queued_file("player1") is None
        assert streaming_server.get_queued_file("player2") is None
