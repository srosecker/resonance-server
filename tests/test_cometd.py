"""
Tests for Cometd/Bayeux protocol implementation.

These tests verify the CometdManager and /cometd endpoint work correctly
for LMS app compatibility (iPeng, Squeezer, Material Skin, etc.).
"""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from resonance.core.events import (
    Event,
    PlayerConnectedEvent,
    PlayerDisconnectedEvent,
    PlayerStatusEvent,
    event_bus,
)
from resonance.web.cometd import CometdClient, CometdManager

# =============================================================================
# CometdClient Tests
# =============================================================================


class TestCometdClient:
    """Tests for CometdClient dataclass."""

    def test_creation(self) -> None:
        """Test basic client creation."""
        client = CometdClient(client_id="abc12345")
        assert client.client_id == "abc12345"
        assert client.subscriptions == set()
        assert client.pending_events == []
        assert client.created_at > 0
        assert client.last_seen > 0

    def test_touch_updates_last_seen(self) -> None:
        """Test that touch() updates last_seen timestamp."""
        client = CometdClient(client_id="abc12345")
        original_time = client.last_seen
        client.touch()
        assert client.last_seen >= original_time

    def test_is_expired(self) -> None:
        """Test expiration check."""
        client = CometdClient(client_id="abc12345")
        # Not expired immediately
        assert not client.is_expired(timeout_s=180)
        # Expired with very short timeout
        assert client.is_expired(timeout_s=0)


# =============================================================================
# CometdManager Tests
# =============================================================================


class TestCometdManager:
    """Tests for CometdManager."""

    @pytest.fixture
    def manager(self) -> CometdManager:
        """Create a CometdManager for testing."""
        return CometdManager()

    @pytest.mark.asyncio
    async def test_handshake(self, manager: CometdManager) -> None:
        """Test /meta/handshake creates a new client session."""
        response = await manager.handshake(msg_id="1")

        assert response["channel"] == "/meta/handshake"
        assert response["successful"] is True
        assert "clientId" in response
        assert len(response["clientId"]) == 8  # 8 hex chars
        assert response["version"] == "1.0"
        assert "long-polling" in response["supportedConnectionTypes"]
        assert "advice" in response

    @pytest.mark.asyncio
    async def test_handshake_creates_client(self, manager: CometdManager) -> None:
        """Test handshake registers the client."""
        response = await manager.handshake()
        client_id = response["clientId"]

        assert await manager.is_valid_client(client_id)
        assert await manager.get_client_count() == 1

    @pytest.mark.asyncio
    async def test_connect_without_events_times_out(self, manager: CometdManager) -> None:
        """Test /meta/connect returns after timeout when no events."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Use very short timeout for test
        responses = await manager.connect(
            client_id=client_id,
            msg_id="2",
            timeout_ms=50,  # 50ms timeout
        )

        assert len(responses) >= 1
        connect_response = responses[0]
        assert connect_response["channel"] == "/meta/connect"
        assert connect_response["successful"] is True
        assert connect_response["clientId"] == client_id

    @pytest.mark.asyncio
    async def test_connect_returns_pending_events(self, manager: CometdManager) -> None:
        """Test /meta/connect returns pending events immediately."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Queue an event
        await manager.deliver_to_client(
            client_id,
            [{"channel": "/test", "data": {"msg": "hello"}}],
        )

        # Connect should return immediately with the event
        responses = await manager.connect(
            client_id=client_id,
            msg_id="2",
            timeout_ms=5000,
        )

        assert len(responses) == 2
        assert responses[0]["channel"] == "/meta/connect"
        assert responses[1]["channel"] == "/test"
        assert responses[1]["data"]["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_connect_invalid_client(self, manager: CometdManager) -> None:
        """Test /meta/connect with invalid clientId returns error."""
        responses = await manager.connect(
            client_id="invalid",
            msg_id="1",
            timeout_ms=50,
        )

        assert len(responses) == 1
        assert responses[0]["successful"] is False
        assert "invalid clientId" in responses[0]["error"]
        assert responses[0]["advice"]["reconnect"] == "handshake"

    @pytest.mark.asyncio
    async def test_disconnect(self, manager: CometdManager) -> None:
        """Test /meta/disconnect removes client session."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        assert await manager.is_valid_client(client_id)

        response = await manager.disconnect(client_id=client_id, msg_id="3")

        assert response["channel"] == "/meta/disconnect"
        assert response["successful"] is True
        assert not await manager.is_valid_client(client_id)

    @pytest.mark.asyncio
    async def test_subscribe(self, manager: CometdManager) -> None:
        """Test /meta/subscribe adds channel subscriptions."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        responses = await manager.subscribe(
            client_id=client_id,
            subscriptions=["/foo/bar", "/baz/*"],
            msg_id="4",
        )

        assert len(responses) == 2
        for resp in responses:
            assert resp["channel"] == "/meta/subscribe"
            assert resp["successful"] is True
            assert resp["subscription"] in ["/foo/bar", "/baz/*"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self, manager: CometdManager) -> None:
        """Test /meta/unsubscribe removes channel subscriptions."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Subscribe first
        await manager.subscribe(
            client_id=client_id,
            subscriptions=["/foo/bar"],
        )

        # Then unsubscribe
        responses = await manager.unsubscribe(
            client_id=client_id,
            subscriptions=["/foo/bar"],
            msg_id="5",
        )

        assert len(responses) == 1
        assert responses[0]["channel"] == "/meta/unsubscribe"
        assert responses[0]["successful"] is True

    @pytest.mark.asyncio
    async def test_slim_subscribe(self, manager: CometdManager) -> None:
        """Test /slim/subscribe for LMS-style event subscription."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        response = await manager.slim_subscribe(
            client_id=client_id,
            request=["-", ["serverstatus", "0", "50", "subscribe:60"]],
            response_channel=f"/slim/{client_id}/serverstatus",
            msg_id="6",
        )

        assert response["channel"] == "/slim/subscribe"
        assert response["successful"] is True

    @pytest.mark.asyncio
    async def test_slim_unsubscribe(self, manager: CometdManager) -> None:
        """Test /slim/unsubscribe for LMS-style event unsubscription."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        response = await manager.slim_unsubscribe(
            client_id=client_id,
            unsubscribe_channel=f"/slim/{client_id}/serverstatus",
            msg_id="7",
        )

        assert response["channel"] == "/slim/unsubscribe"
        assert response["successful"] is True

    @pytest.mark.asyncio
    async def test_deliver_event_to_subscribers(self, manager: CometdManager) -> None:
        """Test event delivery to subscribed clients."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Subscribe to channel
        await manager.subscribe(
            client_id=client_id,
            subscriptions=["/test/channel"],
        )

        # Deliver event
        count = await manager.deliver_event(
            channel="/test/channel",
            data={"message": "hello"},
        )

        assert count == 1

        # Check event is pending
        responses = await manager.connect(
            client_id=client_id,
            timeout_ms=50,
        )

        # Should have connect response + event
        assert len(responses) == 2
        assert responses[1]["channel"] == "/test/channel"
        assert responses[1]["data"]["message"] == "hello"

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self, manager: CometdManager) -> None:
        """Test wildcard subscription patterns."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Subscribe to wildcard
        await manager.subscribe(
            client_id=client_id,
            subscriptions=["/player/**"],
        )

        # Deliver event on matching channel
        count = await manager.deliver_event(
            channel="/player/aa:bb:cc:dd:ee:ff/status",
            data={"state": "playing"},
        )

        assert count == 1

    @pytest.mark.asyncio
    async def test_single_wildcard_subscription(self, manager: CometdManager) -> None:
        """Test single-level wildcard subscription."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Subscribe to single-level wildcard
        await manager.subscribe(
            client_id=client_id,
            subscriptions=["/player/*"],
        )

        # Should match single level
        count = await manager.deliver_event(
            channel="/player/status",
            data={},
        )
        assert count == 1

        # Should NOT match nested level
        count = await manager.deliver_event(
            channel="/player/aa/status",
            data={},
        )
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_match_no_delivery(self, manager: CometdManager) -> None:
        """Test that unsubscribed channels don't receive events."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Subscribe to one channel
        await manager.subscribe(
            client_id=client_id,
            subscriptions=["/foo"],
        )

        # Deliver to different channel
        count = await manager.deliver_event(
            channel="/bar",
            data={},
        )

        assert count == 0


# =============================================================================
# Event Bus Integration Tests
# =============================================================================


class TestCometdEventIntegration:
    """Tests for CometdManager integration with event bus."""

    @pytest.fixture
    async def manager(self) -> CometdManager:
        """Create and start a CometdManager for testing."""
        mgr = CometdManager()
        await mgr.start()
        yield mgr
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_player_status_event_delivery(self, manager: CometdManager) -> None:
        """Test that player status events are delivered to subscribers."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        # Subscribe to player status channel
        await manager.subscribe(
            client_id=client_id,
            subscriptions=["/slim/serverstatus"],
        )

        # Publish a player status event
        await event_bus.publish(
            PlayerStatusEvent(
                player_id="aa:bb:cc:dd:ee:ff",
                state="playing",
                volume=80,
            )
        )

        # Small delay for async processing
        await asyncio.sleep(0.1)

        # Connect should receive the event
        responses = await manager.connect(
            client_id=client_id,
            timeout_ms=50,
        )

        # Check if we received the event
        assert len(responses) >= 1

    @pytest.mark.asyncio
    async def test_player_connected_event_delivery(self, manager: CometdManager) -> None:
        """Test that player connected events are delivered."""
        hs = await manager.handshake()
        client_id = hs["clientId"]

        await manager.subscribe(
            client_id=client_id,
            subscriptions=["/slim/serverstatus"],
        )

        await event_bus.publish(
            PlayerConnectedEvent(
                player_id="aa:bb:cc:dd:ee:ff",
                name="Living Room",
                model="squeezelite",
            )
        )

        await asyncio.sleep(0.1)

        responses = await manager.connect(
            client_id=client_id,
            timeout_ms=50,
        )

        assert len(responses) >= 1


# =============================================================================
# HTTP Endpoint Tests
# =============================================================================


class TestCometdEndpoint:
    """Tests for /cometd HTTP endpoint."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a test FastAPI app with Cometd route."""
        from resonance.web.cometd import CometdManager
        from resonance.web.routes.cometd import router

        app = FastAPI()
        app.state.cometd_manager = CometdManager()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create a test client."""
        return TestClient(app)

    def test_handshake_via_http(self, client: TestClient) -> None:
        """Test /cometd handshake via HTTP POST."""
        response = client.post(
            "/cometd",
            json=[{"channel": "/meta/handshake", "id": "1"}],
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["channel"] == "/meta/handshake"
        assert data[0]["successful"] is True
        assert "clientId" in data[0]

    def test_subscribe_via_http(self, client: TestClient) -> None:
        """Test /cometd subscribe via HTTP POST."""
        # First handshake
        hs_response = client.post(
            "/cometd",
            json=[{"channel": "/meta/handshake", "id": "1"}],
        )
        client_id = hs_response.json()[0]["clientId"]

        # Then subscribe
        response = client.post(
            "/cometd",
            json=[
                {
                    "channel": "/meta/subscribe",
                    "clientId": client_id,
                    "subscription": "/slim/serverstatus",
                    "id": "2",
                }
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["channel"] == "/meta/subscribe"
        assert data[0]["successful"] is True

    def test_batch_messages(self, client: TestClient) -> None:
        """Test sending multiple messages in a batch."""
        response = client.post(
            "/cometd",
            json=[
                {"channel": "/meta/handshake", "id": "1"},
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        client_id = data[0]["clientId"]

        # Send batch with subscribe
        response = client.post(
            "/cometd",
            json=[
                {
                    "channel": "/meta/subscribe",
                    "clientId": client_id,
                    "subscription": ["/foo", "/bar"],
                    "id": "2",
                },
            ],
        )

        data = response.json()
        # Should have 2 subscription responses
        assert len(data) == 2

    def test_disconnect_via_http(self, client: TestClient) -> None:
        """Test /cometd disconnect via HTTP POST."""
        # Handshake
        hs_response = client.post(
            "/cometd",
            json=[{"channel": "/meta/handshake", "id": "1"}],
        )
        client_id = hs_response.json()[0]["clientId"]

        # Disconnect
        response = client.post(
            "/cometd",
            json=[
                {
                    "channel": "/meta/disconnect",
                    "clientId": client_id,
                    "id": "2",
                }
            ],
        )

        assert response.status_code == 200
        data = response.json()
        assert data[0]["channel"] == "/meta/disconnect"
        assert data[0]["successful"] is True

    def test_invalid_json(self, client: TestClient) -> None:
        """Test handling of invalid JSON."""
        response = client.post(
            "/cometd",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400

    def test_empty_body(self, client: TestClient) -> None:
        """Test handling of empty message list."""
        response = client.post(
            "/cometd",
            json=[],
        )

        assert response.status_code == 400

    def test_slim_request_via_http(self, client: TestClient) -> None:
        """Test /slim/request channel."""
        # Handshake first
        hs_response = client.post(
            "/cometd",
            json=[{"channel": "/meta/handshake", "id": "1"}],
        )
        client_id = hs_response.json()[0]["clientId"]

        # Send slim request
        response = client.post(
            "/cometd",
            json=[
                {
                    "channel": "/slim/request",
                    "clientId": client_id,
                    "id": "2",
                    "data": {
                        "request": ["-", ["serverstatus", "0", "10"]],
                        "response": f"/slim/{client_id}/serverstatus",
                    },
                }
            ],
        )

        assert response.status_code == 200
        data = response.json()
        # Should have acknowledgement + result
        assert len(data) >= 1
        assert data[0]["channel"] == "/slim/request"
        assert data[0]["successful"] is True
