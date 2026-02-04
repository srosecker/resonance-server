"""
Tests for resonance.web module (FastAPI + JSON-RPC).

These tests verify:
- FastAPI application setup
- JSON-RPC endpoint functionality
- REST API endpoints
- Proper integration with MusicLibrary and PlayerRegistry

Note on LMS compatibility:
- Some JSON-RPC commands accept `tags:` which controls which fields are returned
  in `*_loop` payloads (field gating). Tests below validate that behavior for a
  minimal, stable subset.
- Phase 2 (small start): year filtering (e.g. "year:2020") should be accepted by
  JSON-RPC commands like `artists`, `albums`, and `titles` and restrict results accordingly.
- Combined filters should behave LMS-like: filters stack (AND), and `count` remains total matches.
- Phase 2 (bigger): genre filtering (e.g. "genre_id:123") should be accepted by
  JSON-RPC commands like `artists`, `albums`, and `titles` and restrict results accordingly.

Seeking notes:
- Direct-stream seeking uses a server-side byte offset heuristic for MP3/FLAC/OGG.
- For MP3, we try to skip ID3v2 tag bytes (so early seeks don't land in metadata).
- If duration is unknown, we fall back to a conservative bytes/sec estimate.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from resonance.core.library import MusicLibrary
from resonance.core.library_db import LibraryDb, UpsertTrack
from resonance.player.registry import PlayerRegistry
from resonance.web.server import WebServer

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def db() -> LibraryDb:
    """Create an in-memory database for testing."""
    db = LibraryDb(":memory:")
    await db.open()
    await db.ensure_schema()
    yield db
    await db.close()


@pytest.fixture
async def library(db: LibraryDb) -> MusicLibrary:
    """Create a MusicLibrary with in-memory DB."""
    lib = MusicLibrary(db=db, music_root=None)
    await lib.initialize()
    return lib


@pytest.fixture
def registry() -> PlayerRegistry:
    """Create a PlayerRegistry for testing."""
    return PlayerRegistry()


@pytest.fixture
async def web_server(registry: PlayerRegistry, library: MusicLibrary) -> WebServer:
    """Create a WebServer instance for testing."""
    server = WebServer(player_registry=registry, music_library=library)
    return server


@pytest.fixture
async def client(web_server: WebServer) -> AsyncClient:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=web_server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for the health check endpoint."""

    async def test_health_check(self, client: AsyncClient) -> None:
        """Test that health check returns ok."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["server"] == "resonance"


# =============================================================================
# Server Status Tests
# =============================================================================


class TestServerStatus:
    """Tests for the server status endpoint."""

    async def test_server_status(self, client: AsyncClient) -> None:
        """Test that server status returns expected info."""
        response = await client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["server"] == "resonance"
        assert data["version"] == "0.1.0"
        assert data["players_connected"] == 0
        assert data["library_initialized"] is True


# =============================================================================
# JSON-RPC Tests
# =============================================================================


class TestJsonRpc:
    """Tests for the JSON-RPC endpoint."""

    async def test_jsonrpc_serverstatus(self, client: AsyncClient) -> None:
        """Test serverstatus command via JSON-RPC."""
        response = await client.post(
            "/jsonrpc.js",
            json={
                "id": 1,
                "method": "slim.request",
                "params": ["-", ["serverstatus"]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["method"] == "slim.request"
        assert "result" in data
        assert data["result"]["version"] == "0.1.0"

    async def test_jsonrpc_players_empty(self, client: AsyncClient) -> None:
        """Test players command with no connected players."""
        response = await client.post(
            "/jsonrpc.js",
            json={
                "id": 2,
                "method": "slim.request",
                "params": ["-", ["players", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["count"] == 0
        assert data["result"]["players_loop"] == []

    async def test_jsonrpc_alternative_endpoint(self, client: AsyncClient) -> None:
        """Test that /jsonrpc (without .js) also works."""
        response = await client.post(
            "/jsonrpc",
            json={
                "id": 3,
                "method": "slim.request",
                "params": ["-", ["serverstatus"]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

    async def test_jsonrpc_unknown_method(self, client: AsyncClient) -> None:
        """Test that unknown method returns error."""
        response = await client.post(
            "/jsonrpc.js",
            json={
                "id": 4,
                "method": "unknown.method",
                "params": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601

    async def test_jsonrpc_invalid_params(self, client: AsyncClient) -> None:
        """Test that invalid params return error."""
        response = await client.post(
            "/jsonrpc.js",
            json={
                "id": 5,
                "method": "slim.request",
                "params": [],  # Missing player_id and command
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32602

    async def test_jsonrpc_artists_empty(self, client: AsyncClient) -> None:
        """Test artists command on empty library."""
        response = await client.post(
            "/jsonrpc.js",
            json={
                "id": 6,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["count"] == 0
        assert data["result"]["artists_loop"] == []

    async def test_jsonrpc_albums_empty(self, client: AsyncClient) -> None:
        """Test albums command on empty library."""
        response = await client.post(
            "/jsonrpc.js",
            json={
                "id": 7,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["count"] == 0
        assert data["result"]["albums_loop"] == []

    async def test_jsonrpc_titles_empty(self, client: AsyncClient) -> None:
        """Test titles command on empty library."""
        response = await client.post(
            "/jsonrpc.js",
            json={
                "id": 8,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["count"] == 0
        assert data["result"]["titles_loop"] == []


# =============================================================================
# JSON-RPC with Library Data Tests
# =============================================================================


class TestJsonRpcWithData:
    """Tests for JSON-RPC with actual library data."""

    @pytest.fixture
    async def populated_client(
        self, db: LibraryDb, library: MusicLibrary, registry: PlayerRegistry
    ) -> AsyncClient:
        """Create a client with some tracks in the library."""
        # Add test tracks
        await db.upsert_tracks(
            [
                # Ensure deterministic genre ids in this fixture:
                # first encountered genre becomes id=1, second becomes id=2, etc.
                UpsertTrack(
                    path="/music/artist1/album1/track1.mp3",
                    title="First Song",
                    artist="Artist One",
                    album="Album One",
                    year=2020,
                    track_no=1,
                    duration_ms=180000,
                    genres=("Rock",),
                ),
                UpsertTrack(
                    path="/music/artist1/album1/track2.mp3",
                    title="Second Song",
                    artist="Artist One",
                    album="Album One",
                    year=2020,
                    track_no=2,
                    duration_ms=200000,
                    genres=("Rock",),
                ),
                # Add a second album for Artist One so sort:albums has a real album_count difference.
                UpsertTrack(
                    path="/music/artist1/album3/track1.mp3",
                    title="Bonus Song",
                    artist="Artist One",
                    album="Album Three",
                    year=2022,
                    track_no=1,
                    duration_ms=210000,
                    genres=("Rock",),
                ),
                UpsertTrack(
                    path="/music/artist2/album2/track1.mp3",
                    title="Another Track",
                    artist="Artist Two",
                    album="Album Two",
                    year=2021,
                    track_no=1,
                    duration_ms=240000,
                    genres=("Jazz",),
                    compilation=True,
                ),
                UpsertTrack(
                    path="/music/artist0/album0/track1.mp3",
                    title="Zed Song",
                    artist="Artist Zero",
                    album="Album Zero",
                    year=2019,
                    track_no=1,
                    duration_ms=150000,
                    genres=("Metal",),
                ),
            ]
        )
        await db.commit()

        from resonance.streaming.server import StreamingServer

        streaming_server = StreamingServer()
        server = WebServer(
            player_registry=registry,
            music_library=library,
            streaming_server=streaming_server,
        )
        transport = ASGITransport(app=server.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    async def test_jsonrpc_genres_with_data(self, populated_client: AsyncClient) -> None:
        """Test genres command with data (count + loop shape)."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 930,
                "method": "slim.request",
                "params": ["-", ["genres", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # From fixture: Rock, Jazz, Metal
        assert data["result"]["count"] == 3
        loop = data["result"]["genres_loop"]
        assert len(loop) == 3

        names = [g["genre"] for g in loop]
        assert "Rock" in names
        assert "Jazz" in names
        assert "Metal" in names

        # Track counts from fixture:
        # Rock: 3 tracks, Jazz: 1, Metal: 1
        by_name = {g["genre"]: g for g in loop}
        assert by_name["Rock"]["tracks"] == 3
        assert by_name["Jazz"]["tracks"] == 1
        assert by_name["Metal"]["tracks"] == 1

    async def test_jsonrpc_genres_tags_gating(self, populated_client: AsyncClient) -> None:
        """genres tags: should gate fields LMS-ish (id always present)."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 931,
                "method": "slim.request",
                "params": ["-", ["genres", 0, 100, "tags:i"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 3
        loop = data["result"]["genres_loop"]
        assert len(loop) == 3

        for item in loop:
            assert "id" in item
            assert "genre" not in item
            assert "tracks" not in item

    async def test_jsonrpc_genres_paging_count_is_total(
        self, populated_client: AsyncClient
    ) -> None:
        """genres paging: count must be total matches, not page size."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 932,
                "method": "slim.request",
                "params": ["-", ["genres", 0, 1]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 3
        assert len(data["result"]["genres_loop"]) == 1

    # -------------------------------------------------------------------------
    # roles command tests (Phase 3: Role Discovery)
    # -------------------------------------------------------------------------

    async def test_jsonrpc_roles_discovery(self, populated_client: AsyncClient) -> None:
        """Test roles command returns seeded roles for discovery."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 940,
                "method": "slim.request",
                "params": ["-", ["roles", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Seeded roles: artist, albumartist, composer, conductor, band
        assert data["result"]["count"] == 5
        loop = data["result"]["roles_loop"]
        assert len(loop) == 5

        # All items must have role_id (always present)
        for item in loop:
            assert "role_id" in item
            assert isinstance(item["role_id"], int)

    async def test_jsonrpc_roles_tags_gating(self, populated_client: AsyncClient) -> None:
        """roles tags:t should include role_name."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 941,
                "method": "slim.request",
                "params": ["-", ["roles", 0, 100, "tags:t"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 5
        loop = data["result"]["roles_loop"]
        assert len(loop) == 5

        # With tags:t, role_name should be present
        names = [item.get("role_name") for item in loop]
        assert "artist" in names
        assert "albumartist" in names
        assert "composer" in names
        assert "conductor" in names
        assert "band" in names

    async def test_jsonrpc_roles_paging_count_is_total(self, populated_client: AsyncClient) -> None:
        """roles paging: count must be total matches, not page size."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 942,
                "method": "slim.request",
                "params": ["-", ["roles", 0, 2]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # count is total (5 seeded roles), loop is limited to page size (2)
        assert data["result"]["count"] == 5
        assert len(data["result"]["roles_loop"]) == 2

    async def test_jsonrpc_artists_with_data(self, populated_client: AsyncClient) -> None:
        """Test artists command with data."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 1,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["count"] == 3
        artists = [a["artist"] for a in data["result"]["artists_loop"]]
        assert "Artist One" in artists
        assert "Artist Two" in artists
        assert "Artist Zero" in artists

    async def test_jsonrpc_albums_with_data(self, populated_client: AsyncClient) -> None:
        """Test albums command with data."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 2,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["count"] == 4
        albums = [a["album"] for a in data["result"]["albums_loop"]]
        assert "Album One" in albums
        assert "Album Two" in albums
        assert "Album Zero" in albums
        assert "Album Three" in albums

    async def test_jsonrpc_artists_filter_by_genre_id(self, populated_client: AsyncClient) -> None:
        """
        artists genre_id:<id> should restrict artists to those having tracks in that genre.

        Fixture mapping (deterministic in this test DB):
        - genre_id:1 => Rock (Artist One)
        - genre_id:2 => Jazz (Artist Two)
        - genre_id:3 => Metal (Artist Zero)
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 920,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100, "genre_id:1"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["artists_loop"]
        assert len(loop) == 1
        assert loop[0]["artist"] == "Artist One"

    async def test_jsonrpc_albums_filter_by_genre_id(self, populated_client: AsyncClient) -> None:
        """
        albums genre_id:<id> should restrict albums to those having tracks in that genre.

        genre_id:1 => Rock, which exists on Album One + Album Three in fixture.
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 921,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, "genre_id:1"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 2
        albums = [a["album"] for a in data["result"]["albums_loop"]]
        assert "Album One" in albums
        assert "Album Three" in albums

    async def test_jsonrpc_titles_filter_by_genre_id(self, populated_client: AsyncClient) -> None:
        """
        titles genre_id:<id> should restrict titles to those in that genre.

        genre_id:1 => Rock, which exists on 3 tracks in fixture:
        - First Song
        - Second Song
        - Bonus Song
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 922,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, "genre_id:1"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 3
        titles = [t["title"] for t in data["result"]["titles_loop"]]
        assert "First Song" in titles
        assert "Second Song" in titles
        assert "Bonus Song" in titles

    async def test_jsonrpc_albums_filter_by_compilation(
        self, populated_client: AsyncClient
    ) -> None:
        """
        albums compilation:1 should restrict albums to compilation albums.

        Fixture:
        - Album Two is marked compilation=True (track-level), aggregated to album-level.
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 940,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, "compilation:1"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["albums_loop"]
        assert len(loop) == 1
        assert loop[0]["album"] == "Album Two"

    async def test_jsonrpc_albums_filter_by_compilation_and_genre_id(
        self, populated_client: AsyncClient
    ) -> None:
        """
        albums compilation:1 + genre_id:<id> should AND-filter (intersection).

        We discover the concrete genre_id via the genres command to avoid relying on
        implicit AUTOINCREMENT ordering.
        """
        # Discover Jazz genre_id via genres listing
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 9410,
                "method": "slim.request",
                "params": ["-", ["genres", 0, 100]],
            },
        )
        assert response.status_code == 200
        genres_data = response.json()
        jazz = next(g for g in genres_data["result"]["genres_loop"] if g["genre"] == "Jazz")
        jazz_id = jazz["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 942,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, "compilation:1", f"genre_id:{jazz_id}"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["albums_loop"]
        assert len(loop) == 1
        assert loop[0]["album"] == "Album Two"

    async def test_jsonrpc_albums_filter_by_compilation_and_year(
        self, populated_client: AsyncClient
    ) -> None:
        """
        albums compilation:1 + year:<yyyy> should AND-filter (intersection).

        Fixture:
        - Album Two is compilation=True and has year=2021.
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 948,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, "compilation:1", "year:2021"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["albums_loop"]
        assert len(loop) == 1
        assert loop[0]["album"] == "Album Two"

    async def test_jsonrpc_artists_filter_by_compilation(
        self, populated_client: AsyncClient
    ) -> None:
        """
        artists compilation:1 should restrict artists to those having at least one compilation track.

        Fixture:
        - Only Artist Two has a compilation=True track ("Another Track").
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 951,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100, "compilation:1"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["artists_loop"]
        assert len(loop) == 1
        assert loop[0]["artist"] == "Artist Two"

    async def test_jsonrpc_albums_filter_by_compilation_and_artist_id(
        self, populated_client: AsyncClient
    ) -> None:
        """
        albums compilation:1 + artist_id:<id> should AND-filter (intersection).

        Fixture:
        - Album Two is compilation=True and belongs to Artist Two.
        """
        # Fetch artists to obtain Artist Two id
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 949,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        artist_two = next(a for a in data["result"]["artists_loop"] if a["artist"] == "Artist Two")
        artist_id = artist_two["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 950,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, "compilation:1", f"artist_id:{artist_id}"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["albums_loop"]
        assert len(loop) == 1
        assert loop[0]["album"] == "Album Two"

    async def test_jsonrpc_titles_filter_by_genre_id_and_year(
        self, populated_client: AsyncClient
    ) -> None:
        """
        titles genre_id:<id> + year:<yyyy> should AND-filter (intersection).

        Fixture:
        - Rock (genre_id:1) tracks are in 2020 and 2022.
        - For year:2020, only the two Album One tracks match.
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 933,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, "genre_id:1", "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 2
        titles = [t["title"] for t in data["result"]["titles_loop"]]
        assert "First Song" in titles
        assert "Second Song" in titles
        assert "Bonus Song" not in titles

    async def test_jsonrpc_titles_filter_by_compilation_and_genre_id(
        self, populated_client: AsyncClient
    ) -> None:
        """
        titles compilation:1 + genre_id:<id> should AND-filter (intersection).

        We discover the concrete genre_id via the genres command to avoid relying on
        implicit AUTOINCREMENT ordering.
        """
        # Discover Jazz genre_id via genres listing
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 9411,
                "method": "slim.request",
                "params": ["-", ["genres", 0, 100]],
            },
        )
        assert response.status_code == 200
        genres_data = response.json()
        jazz = next(g for g in genres_data["result"]["genres_loop"] if g["genre"] == "Jazz")
        jazz_id = jazz["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 941,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, "compilation:1", f"genre_id:{jazz_id}"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["titles_loop"]
        assert len(loop) == 1
        assert loop[0]["title"] == "Another Track"

    async def test_jsonrpc_titles_filter_by_compilation_and_year(
        self, populated_client: AsyncClient
    ) -> None:
        """
        titles compilation:1 + year:<yyyy> should AND-filter (intersection).

        Fixture:
        - Only "Another Track" is compilation=True and has year=2021.
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 943,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, "compilation:1", "year:2021"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["titles_loop"]
        assert len(loop) == 1
        assert loop[0]["title"] == "Another Track"

    async def test_jsonrpc_titles_filter_by_compilation_and_artist_id(
        self, populated_client: AsyncClient
    ) -> None:
        """
        titles compilation:1 + artist_id:<id> should AND-filter (intersection).

        Fixture:
        - Only Artist Two has a compilation track ("Another Track").
        """
        # Fetch artists to obtain Artist Two id
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 944,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        artist_two = next(a for a in data["result"]["artists_loop"] if a["artist"] == "Artist Two")
        artist_id = artist_two["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 945,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, "compilation:1", f"artist_id:{artist_id}"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["titles_loop"]
        assert len(loop) == 1
        assert loop[0]["title"] == "Another Track"

    async def test_jsonrpc_titles_filter_by_compilation_and_album_id(
        self, populated_client: AsyncClient
    ) -> None:
        """
        titles compilation:1 + album_id:<id> should AND-filter (intersection).

        Fixture:
        - "Another Track" is on Album Two, which is compilation=True.
        """
        # Fetch albums to obtain Album Two id
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 946,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        album_two = next(a for a in data["result"]["albums_loop"] if a["album"] == "Album Two")
        album_id = album_two["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 947,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, "compilation:1", f"album_id:{album_id}"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["titles_loop"]
        assert len(loop) == 1
        assert loop[0]["title"] == "Another Track"

    async def test_jsonrpc_titles_filter_by_genre_id_and_artist_id(
        self, populated_client: AsyncClient
    ) -> None:
        """
        titles genre_id:<id> + artist_id:<id> should AND-filter (intersection).

        Fixture:
        - Rock (genre_id:1) belongs to Artist One only.
        - Therefore filtering by (Rock + Artist One) returns 3 tracks.
        """
        # Fetch artists to obtain Artist One id
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 934,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        artist_one = next(a for a in data["result"]["artists_loop"] if a["artist"] == "Artist One")
        artist_id = artist_one["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 935,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, f"genre_id:1", f"artist_id:{artist_id}"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 3
        titles = [t["title"] for t in data["result"]["titles_loop"]]
        assert "First Song" in titles
        assert "Second Song" in titles
        assert "Bonus Song" in titles

    async def test_jsonrpc_albums_filter_by_genre_id_and_year(
        self, populated_client: AsyncClient
    ) -> None:
        """
        albums genre_id:<id> + year:<yyyy> should AND-filter (intersection).

        Fixture:
        - Rock (genre_id:1) albums are Album One (2020) and Album Three (2022).
        - For year:2020, only Album One matches.
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 936,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, "genre_id:1", "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 1
        loop = data["result"]["albums_loop"]
        assert len(loop) == 1
        assert loop[0]["album"] == "Album One"

    async def test_jsonrpc_artists_filter_by_year(self, populated_client: AsyncClient) -> None:
        """artists year:<yyyy> should restrict artists to those having tracks in that year."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 912,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100, "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # In fixture data, only Artist One has tracks in year=2020.
        assert data["result"]["count"] == 1
        loop = data["result"]["artists_loop"]
        assert len(loop) == 1
        assert loop[0]["artist"] == "Artist One"

    async def test_jsonrpc_albums_filter_by_year(self, populated_client: AsyncClient) -> None:
        """albums year:<yyyy> should restrict albums to that year."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 910,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        albums = data["result"]["albums_loop"]
        # In fixture data, only Album One is year=2020.
        assert data["result"]["count"] == 1
        assert len(albums) == 1
        assert albums[0]["album"] == "Album One"
        assert albums[0]["year"] == 2020

    async def test_jsonrpc_albums_filter_by_artist_id_and_year(
        self, populated_client: AsyncClient
    ) -> None:
        """albums artist_id:<id> + year:<yyyy> should AND-filter (intersection)."""
        # First fetch artists to obtain Artist One id
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 913,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        artist_one = next(a for a in data["result"]["artists_loop"] if a["artist"] == "Artist One")
        artist_id = artist_one["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 914,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100, f"artist_id:{artist_id}", "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Artist One has albums in 2020 (Album One) and 2022 (Album Three) -> intersection w/ 2020 is 1 album.
        assert data["result"]["count"] == 1
        albums = data["result"]["albums_loop"]
        assert len(albums) == 1
        assert albums[0]["album"] == "Album One"
        assert albums[0]["year"] == 2020

    async def test_jsonrpc_titles_with_data(self, populated_client: AsyncClient) -> None:
        """Test titles command with data."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 3,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["count"] == 5
        titles = [t["title"] for t in data["result"]["titles_loop"]]
        assert "First Song" in titles
        assert "Second Song" in titles
        assert "Another Track" in titles
        assert "Zed Song" in titles

    async def test_jsonrpc_titles_filter_by_year(self, populated_client: AsyncClient) -> None:
        """titles year:<yyyy> should restrict tracks to that year."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 911,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        titles_loop = data["result"]["titles_loop"]
        titles = [t["title"] for t in titles_loop]

        # In fixture data, the two tracks from Album One are year=2020.
        assert data["result"]["count"] == 2
        assert set(titles) == {"First Song", "Second Song"}
        assert all(t.get("year") == 2020 for t in titles_loop)

    async def test_jsonrpc_titles_filter_by_artist_id_and_year(
        self, populated_client: AsyncClient
    ) -> None:
        """titles artist_id:<id> + year:<yyyy> should AND-filter (intersection)."""
        # First fetch artists to obtain Artist One id
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 915,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        artist_one = next(a for a in data["result"]["artists_loop"] if a["artist"] == "Artist One")
        artist_id = artist_one["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 916,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, f"artist_id:{artist_id}", "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        titles_loop = data["result"]["titles_loop"]
        titles = [t["title"] for t in titles_loop]

        # Artist One has 2020 tracks (First/Second) and a 2022 track (Bonus). Intersection w/ 2020 is 2.
        assert data["result"]["count"] == 2
        assert set(titles) == {"First Song", "Second Song"}
        assert all(t.get("year") == 2020 for t in titles_loop)

    async def test_jsonrpc_titles_filter_by_album_id_and_year(
        self, populated_client: AsyncClient
    ) -> None:
        """titles album_id:<id> + year:<yyyy> should AND-filter (intersection)."""
        # Fetch albums to obtain Album One id
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 917,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 100]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        album_one = next(a for a in data["result"]["albums_loop"] if a.get("album") == "Album One")
        album_id = album_one["id"]

        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 918,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 100, f"album_id:{album_id}", "year:2020"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        titles_loop = data["result"]["titles_loop"]
        titles = [t["title"] for t in titles_loop]

        # Album One is 2020, so intersection should still be Album One's two tracks.
        assert data["result"]["count"] == 2
        assert set(titles) == {"First Song", "Second Song"}
        assert all(t.get("year") == 2020 for t in titles_loop)

    async def test_jsonrpc_artists_paging_count_is_total(
        self, populated_client: AsyncClient
    ) -> None:
        """LMS-style: count is total matches, not page size (artists)."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 200,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 1]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # We inserted 3 artists in the fixture, but requested only 1 item.
        assert data["result"]["count"] == 3
        assert len(data["result"]["artists_loop"]) == 1

    async def test_jsonrpc_artists_sort_artist_orders_by_name(
        self, populated_client: AsyncClient
    ) -> None:
        """artists sort:artist should order alphabetically by artist name."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 202,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100, "sort:artist"]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        artists = [a["artist"] for a in data["result"]["artists_loop"]]
        # Alphabetical: Artist One, Artist Two, Artist Zero
        assert artists == ["Artist One", "Artist Two", "Artist Zero"]

    async def test_jsonrpc_artists_sort_id_orders_by_id(
        self, populated_client: AsyncClient
    ) -> None:
        """artists sort:id should order by stable numeric artist id."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 203,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100, "sort:id"]],
            },
        )
        assert response.status_code == 200
        data = response.json()
        ids = [a["id"] for a in data["result"]["artists_loop"]]
        assert ids == sorted(ids)

    async def test_jsonrpc_artists_sort_albums_orders_by_album_count_desc(
        self, populated_client: AsyncClient
    ) -> None:
        """artists sort:albums should order by album count desc, then name."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 204,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 100, "sort:albums"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Artist One has 2 albums, the others have 1 => Artist One must be ranked first.
        artists = [a["artist"] for a in data["result"]["artists_loop"]]
        assert artists[0] == "Artist One"

    async def test_jsonrpc_albums_paging_count_is_total(
        self, populated_client: AsyncClient
    ) -> None:
        """LMS-style: count is total matches, not page size (albums)."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 201,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 1]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Fixture inserts 4 distinct albums; we requested only 1 item.
        assert data["result"]["count"] == 4
        assert len(data["result"]["albums_loop"]) == 1

    async def test_jsonrpc_titles_paging_count_is_total(
        self, populated_client: AsyncClient
    ) -> None:
        """LMS-style: count is total matches, not page size (titles)."""
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 202,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 1]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Fixture inserts 5 tracks; we requested only 1 item.
        assert data["result"]["count"] == 5
        assert len(data["result"]["titles_loop"]) == 1

    async def test_jsonrpc_artists_tags_field_gating_minimal(
        self, populated_client: AsyncClient
    ) -> None:
        """
        artists tags: should gate returned fields.

        We request only id + artist name:
        - i => id
        - a => artist
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 900,
                "method": "slim.request",
                "params": ["-", ["artists", 0, 1, "tags:ia"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 3
        loop = data["result"]["artists_loop"]
        assert len(loop) == 1

        item = loop[0]
        assert "id" in item
        assert "artist" in item
        assert "albums" not in item

    async def test_jsonrpc_albums_tags_field_gating_minimal(
        self, populated_client: AsyncClient
    ) -> None:
        """
        albums tags: should gate returned fields.

        We request only:
        - i => id
        - l => album title
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 901,
                "method": "slim.request",
                "params": ["-", ["albums", 0, 1, "tags:il"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 4
        loop = data["result"]["albums_loop"]
        assert len(loop) == 1

        item = loop[0]
        assert "id" in item
        assert "album" in item
        assert "artist" not in item
        assert "year" not in item
        assert "tracks" not in item
        assert "artist_id" not in item

    async def test_jsonrpc_titles_tags_field_gating_minimal_includes_url(
        self, populated_client: AsyncClient
    ) -> None:
        """
        titles tags: should gate returned fields.

        We request only id + title. In addition, servers typically must include `url`
        for playback/navigation, so we allow `url` to be present even if not requested.
        """
        response = await populated_client.post(
            "/jsonrpc.js",
            json={
                "id": 902,
                "method": "slim.request",
                "params": ["-", ["titles", 0, 1, "tags:it"]],
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["result"]["count"] == 5
        loop = data["result"]["titles_loop"]
        assert len(loop) == 1

        item = loop[0]
        assert "id" in item
        assert "title" in item

        # `url` is required by many clients; allow as always-present.
        assert "url" in item

        # Gated fields should not be present when not requested.
        assert "artist" not in item
        assert "album" not in item
        assert "year" not in item
        assert "duration" not in item
        assert "tracknum" not in item
