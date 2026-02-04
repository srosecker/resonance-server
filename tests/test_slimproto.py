"""
Tests for the Slimproto protocol server.

These tests verify the core functionality of the Slimproto server including
connection handling, HELO parsing, and message dispatch.
"""

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resonance.player.client import DeviceType, PlayerClient, PlayerState
from resonance.player.registry import PlayerRegistry
from resonance.protocol.slimproto import (
    DEVICE_IDS,
    ProtocolError,
    SlimprotoServer,
)

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def player_registry() -> PlayerRegistry:
    """Create a fresh player registry for testing."""
    return PlayerRegistry()


@pytest.fixture
def slimproto_server(player_registry: PlayerRegistry) -> SlimprotoServer:
    """Create a Slimproto server instance for testing."""
    return SlimprotoServer(
        host="127.0.0.1",
        port=0,  # Let OS assign port
        player_registry=player_registry,
    )


@pytest.fixture
def mock_reader() -> AsyncMock:
    """Create a mock StreamReader."""
    reader = AsyncMock(spec=asyncio.StreamReader)
    return reader


@pytest.fixture
def mock_writer() -> MagicMock:
    """Create a mock StreamWriter."""
    writer = MagicMock(spec=asyncio.StreamWriter)
    writer.get_extra_info = MagicMock(return_value=("192.168.1.100", 54321))
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return writer


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def build_helo_message(
    device_id: int = 12,  # squeezeplay
    revision: int = 1,
    mac: bytes = b"\x00\x04\x20\x12\x34\x56",
    uuid: bytes = b"",
    capabilities: str = "",
) -> bytes:
    """Build a HELO message payload for testing."""
    payload = bytes([device_id, revision]) + mac

    if uuid:
        payload += uuid

    # Add padding to reach minimum length
    while len(payload) < 20:
        payload += b"\x00"

    if capabilities:
        # Ensure we're at capabilities offset
        while len(payload) < 36:
            payload += b"\x00"
        payload += capabilities.encode("utf-8")

    return payload


def build_stat_message(
    event_code: str = "STMt",
    buffer_fullness: int = 0,
    elapsed_seconds: int = 0,
    elapsed_ms: int = 0,
) -> bytes:
    """Build a STAT message payload for testing.

    Format (per slimproto.py):
        [0-3]   Event code (4 bytes)
        [4]     CRLF count (1 byte)
        [5]     MAS initialized (1 byte)
        [6]     MAS mode (1 byte)
        [7-10]  Buffer size (4 bytes)
        [11-14] Data in buffer / buffer_fullness (4 bytes)
        [15-22] Bytes received (8 bytes)
        [23-24] Signal strength (2 bytes)
        [25-28] Jiffies (4 bytes)
        [29-32] Output buffer size (4 bytes)
        [33-36] Output buffer fullness (4 bytes)
        [37-40] Elapsed seconds (4 bytes)
        [41-42] Voltage (2 bytes)
        [43-46] Elapsed milliseconds (4 bytes)
    """
    payload = event_code.encode("ascii")  # bytes 0-3
    payload += b"\x00" * 3  # bytes 4-6: CRLF, MAS init, MAS mode
    payload += struct.pack(">I", 0)  # bytes 7-10: buffer size
    payload += struct.pack(">I", buffer_fullness)  # bytes 11-14
    payload += struct.pack(">Q", 0)  # bytes 15-22: bytes received
    payload += struct.pack(">H", 50)  # bytes 23-24: signal strength
    payload += struct.pack(">I", 0)  # bytes 25-28: jiffies
    payload += struct.pack(">I", 0)  # bytes 29-32: output buffer size
    payload += struct.pack(">I", 0)  # bytes 33-36: output buffer fullness
    payload += struct.pack(">I", elapsed_seconds)  # bytes 37-40: elapsed seconds
    payload += struct.pack(">H", 0)  # bytes 41-42: voltage
    payload += struct.pack(">I", elapsed_ms)  # bytes 43-46: elapsed ms

    return payload


def build_slimproto_message(command: str, payload: bytes) -> bytes:
    """Build a complete Slimproto message with header."""
    header = command.encode("ascii") + struct.pack(">I", len(payload))
    return header + payload


# -----------------------------------------------------------------------------
# Server Lifecycle Tests
# -----------------------------------------------------------------------------


class TestSlimprotoServerLifecycle:
    """Tests for server start/stop lifecycle."""

    async def test_server_starts_and_stops(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Server should start and stop cleanly."""
        assert not slimproto_server.is_running

        await slimproto_server.start()
        assert slimproto_server.is_running

        await slimproto_server.stop()
        assert not slimproto_server.is_running

    async def test_server_can_restart(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Server should be able to restart after stopping."""
        await slimproto_server.start()
        await slimproto_server.stop()

        await slimproto_server.start()
        assert slimproto_server.is_running

        await slimproto_server.stop()

    async def test_double_start_is_safe(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Starting an already running server should be safe."""
        await slimproto_server.start()
        await slimproto_server.start()  # Should not raise
        assert slimproto_server.is_running

        await slimproto_server.stop()

    async def test_double_stop_is_safe(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Stopping an already stopped server should be safe."""
        await slimproto_server.start()
        await slimproto_server.stop()
        await slimproto_server.stop()  # Should not raise


# -----------------------------------------------------------------------------
# HELO Parsing Tests
# -----------------------------------------------------------------------------


class TestHeloParsing:
    """Tests for HELO message parsing."""

    def test_parse_basic_helo(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """Should parse basic HELO with MAC address."""
        client = PlayerClient(mock_reader, mock_writer)
        payload = build_helo_message(
            device_id=12,
            revision=42,
            mac=b"\xaa\xbb\xcc\xdd\xee\xff",
        )

        slimproto_server._parse_helo(client, payload)

        assert client.id == "aa:bb:cc:dd:ee:ff"
        assert client.info.mac_address == "aa:bb:cc:dd:ee:ff"
        assert client.info.device_type == DeviceType.SQUEEZEPLAY
        assert client.info.firmware_version == "42"
        assert client.status.state == PlayerState.CONNECTED

    def test_parse_helo_with_uuid(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """Should parse HELO with UUID (36+ bytes)."""
        client = PlayerClient(mock_reader, mock_writer)

        # Build HELO with UUID
        device_id = 12
        revision = 1
        mac = b"\x00\x04\x20\x12\x34\x56"
        uuid = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10"

        payload = bytes([device_id, revision]) + mac + uuid
        # Pad to 36 bytes
        while len(payload) < 36:
            payload += b"\x00"

        slimproto_server._parse_helo(client, payload)

        assert client.id == "00:04:20:12:34:56"
        assert client.info.uuid == "0102030405060708090a0b0c0d0e0f10"

    def test_parse_helo_with_capabilities(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """Should parse HELO with capabilities string."""
        client = PlayerClient(mock_reader, mock_writer)
        payload = build_helo_message(
            device_id=12,
            capabilities="Name=Living Room,Model=squeezelite,MaxSampleRate=192000",
        )

        slimproto_server._parse_helo(client, payload)

        assert client.info.name == "Living Room"
        assert "Model" in client.info.capabilities
        assert client.info.capabilities["Model"] == "squeezelite"
        assert client.info.capabilities["MaxSampleRate"] == "192000"

    def test_parse_helo_all_device_types(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """Should correctly identify all known device types."""
        for device_id, device_name in DEVICE_IDS.items():
            client = PlayerClient(mock_reader, mock_writer)
            payload = build_helo_message(device_id=device_id)

            slimproto_server._parse_helo(client, payload)

            assert client.info.model == device_name

    def test_parse_helo_unknown_device(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """Should handle unknown device IDs gracefully."""
        client = PlayerClient(mock_reader, mock_writer)
        payload = build_helo_message(device_id=99)  # Unknown

        slimproto_server._parse_helo(client, payload)

        assert client.info.device_type == DeviceType.UNKNOWN
        assert "unknown" in client.info.model

    def test_parse_helo_too_short(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """Should raise error for too-short HELO."""
        client = PlayerClient(mock_reader, mock_writer)
        payload = b"\x00\x01\x02"  # Only 3 bytes

        with pytest.raises(ProtocolError, match="too short"):
            slimproto_server._parse_helo(client, payload)


# -----------------------------------------------------------------------------
# STAT Handling Tests
# -----------------------------------------------------------------------------


class TestStatHandling:
    """Tests for STAT message handling."""

    async def test_handle_stat_updates_status(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """STAT should update client status fields."""
        client = PlayerClient(mock_reader, mock_writer)
        client._id = "00:04:20:12:34:56"

        payload = build_stat_message(
            event_code="STMt",
            buffer_fullness=8192,
            elapsed_seconds=120,
            elapsed_ms=120500,
        )

        await slimproto_server._handle_stat(client, payload)

        assert client.status.buffer_fullness == 8192
        assert client.status.elapsed_seconds == 120

    async def test_handle_stat_playing_state(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """STAT with STMr should set playing state."""
        client = PlayerClient(mock_reader, mock_writer)
        client._id = "00:04:20:12:34:56"

        payload = build_stat_message(event_code="STMr")
        await slimproto_server._handle_stat(client, payload)

        assert client.status.state == PlayerState.PLAYING

    async def test_handle_stat_paused_state(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """STAT with STMp should set paused state."""
        client = PlayerClient(mock_reader, mock_writer)
        client._id = "00:04:20:12:34:56"

        payload = build_stat_message(event_code="STMp")
        await slimproto_server._handle_stat(client, payload)

        assert client.status.state == PlayerState.PAUSED

    async def test_handle_stat_stopped_state(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """STAT with STMs should set stopped state."""
        client = PlayerClient(mock_reader, mock_writer)
        client._id = "00:04:20:12:34:56"

        payload = build_stat_message(event_code="STMs")
        await slimproto_server._handle_stat(client, payload)

        assert client.status.state == PlayerState.STOPPED

    async def test_handle_stat_short_payload(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """Should handle too-short STAT gracefully."""
        client = PlayerClient(mock_reader, mock_writer)
        client._id = "00:04:20:12:34:56"

        # Only 10 bytes, minimum is 36
        payload = b"STMt" + b"\x00" * 6

        # Should not raise, just log warning
        await slimproto_server._handle_stat(client, payload)


# -----------------------------------------------------------------------------
# BYE Handling Tests
# -----------------------------------------------------------------------------


class TestByeHandling:
    """Tests for BYE! message handling."""

    async def test_handle_bye_disconnects_player(
        self,
        slimproto_server: SlimprotoServer,
        mock_reader: AsyncMock,
        mock_writer: MagicMock,
    ) -> None:
        """BYE! should set player state to disconnected."""
        client = PlayerClient(mock_reader, mock_writer)
        client._id = "00:04:20:12:34:56"
        client.status.state = PlayerState.PLAYING

        await slimproto_server._handle_bye(client, b"")

        assert client.status.state == PlayerState.DISCONNECTED


# -----------------------------------------------------------------------------
# Message Reading Tests
# -----------------------------------------------------------------------------


class TestMessageReading:
    """Tests for reading Slimproto messages."""

    async def test_read_message_success(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should correctly read a valid message."""
        reader = AsyncMock()
        payload = b"test payload data"
        message = build_slimproto_message("TEST", payload)

        # Mock readexactly to return header then payload
        reader.readexactly = AsyncMock(
            side_effect=[
                message[:8],  # Header
                payload,  # Payload
            ]
        )

        command, data = await slimproto_server._read_message(reader)

        assert command == "TEST"
        assert data == payload

    async def test_read_message_empty_payload(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should handle messages with zero-length payload."""
        reader = AsyncMock()
        header = b"BYE!" + struct.pack(">I", 0)
        reader.readexactly = AsyncMock(return_value=header)

        command, data = await slimproto_server._read_message(reader)

        assert command == "BYE!"
        assert data == b""

    async def test_read_message_too_large(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should reject messages larger than max size."""
        reader = AsyncMock()
        # Claim a payload of 1MB (exceeds 64KB limit)
        header = b"TEST" + struct.pack(">I", 1024 * 1024)
        reader.readexactly = AsyncMock(return_value=header)

        with pytest.raises(ProtocolError, match="too large"):
            await slimproto_server._read_message(reader)


# -----------------------------------------------------------------------------
# Capabilities Parsing Tests
# -----------------------------------------------------------------------------


class TestCapabilitiesParsing:
    """Tests for capabilities string parsing."""

    def test_parse_simple_capabilities(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should parse key=value pairs."""
        caps = slimproto_server._parse_capabilities("Name=Test,Model=squeezelite")

        assert caps["Name"] == "Test"
        assert caps["Model"] == "squeezelite"

    def test_parse_capabilities_with_flags(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should handle flags without values."""
        caps = slimproto_server._parse_capabilities("HasDisplay,CanSync,Name=Test")

        assert caps["HasDisplay"] == "1"
        assert caps["CanSync"] == "1"
        assert caps["Name"] == "Test"

    def test_parse_empty_capabilities(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should handle empty string."""
        caps = slimproto_server._parse_capabilities("")

        assert caps == {}

    def test_parse_capabilities_with_equals_in_value(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should handle values containing equals signs."""
        caps = slimproto_server._parse_capabilities("Equation=a=b+c")

        assert caps["Equation"] == "a=b+c"


# -----------------------------------------------------------------------------
# Player Registry Integration Tests
# -----------------------------------------------------------------------------


class TestPlayerRegistryIntegration:
    """Tests for player registry integration."""

    async def test_player_registered_after_helo(
        self,
        player_registry: PlayerRegistry,
    ) -> None:
        """Player should be registered after successful HELO."""
        server = SlimprotoServer(
            host="127.0.0.1",
            port=0,
            player_registry=player_registry,
        )

        reader = AsyncMock()
        writer = MagicMock()
        writer.get_extra_info = MagicMock(return_value=("192.168.1.100", 54321))
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        client = PlayerClient(reader, writer)
        payload = build_helo_message(mac=b"\xaa\xbb\xcc\xdd\xee\xff")
        server._parse_helo(client, payload)

        await player_registry.register(client)

        assert len(player_registry) == 1
        found = await player_registry.get_by_mac("aa:bb:cc:dd:ee:ff")
        assert found is not None
        assert found.id == "aa:bb:cc:dd:ee:ff"

    async def test_send_to_player(
        self,
        player_registry: PlayerRegistry,
    ) -> None:
        """Should be able to send message to registered player."""
        server = SlimprotoServer(
            host="127.0.0.1",
            port=0,
            player_registry=player_registry,
        )

        reader = AsyncMock()
        writer = MagicMock()
        writer.get_extra_info = MagicMock(return_value=("192.168.1.100", 54321))
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()

        client = PlayerClient(reader, writer)
        client._id = "aa:bb:cc:dd:ee:ff"
        client.info.mac_address = "aa:bb:cc:dd:ee:ff"
        client.status.state = PlayerState.CONNECTED

        await player_registry.register(client)

        result = await server.send_to_player("aa:bb:cc:dd:ee:ff", "test", b"payload")

        assert result is True
        writer.write.assert_called()

    async def test_send_to_unknown_player(
        self,
        slimproto_server: SlimprotoServer,
    ) -> None:
        """Should return False when sending to unknown player."""
        result = await slimproto_server.send_to_player(
            "ff:ff:ff:ff:ff:ff",
            "test",
            b"",
        )

        assert result is False
