"""
Slimproto Protocol Server for Resonance.

This module implements the Slimproto binary protocol used by Squeezebox
players to communicate with the server. The protocol runs on TCP port 3483.

Protocol Format:
    Messages consist of a 4-byte ASCII command tag, followed by a 4-byte
    big-endian length field, followed by the payload data.

    [COMMAND: 4 bytes][LENGTH: 4 bytes][PAYLOAD: LENGTH bytes]

Reference: Slim/Networking/Slimproto.pm from the original LMS
"""

import asyncio
import ipaddress
import logging
import socket
import struct
from collections.abc import Callable, Coroutine
from typing import Any

from resonance.core.events import (
    PlayerConnectedEvent,
    PlayerDisconnectedEvent,
    PlayerStatusEvent,
    PlayerTrackFinishedEvent,
    event_bus,
)
from resonance.player.client import DeviceType, PlayerClient, PlayerState
from resonance.player.registry import PlayerRegistry
from resonance.protocol.commands import (
    AudioFormat,
    AutostartMode,
    StreamParams,
    build_stream_pause,
    build_stream_stop,
    build_stream_unpause,
    build_strm_frame,
    build_volume_frame,
)

logger = logging.getLogger(__name__)

# When enabled, outgoing frames include a compact hexdump for easier debugging.
OUTGOING_FRAME_DEBUG = True
OUTGOING_FRAME_HEXDUMP_BYTES = 64


def _hexdump(data: bytes, limit: int = OUTGOING_FRAME_HEXDUMP_BYTES) -> str:
    """Return a compact hex representation of the first N bytes."""
    view = data[:limit]
    hexpart = " ".join(f"{b:02x}" for b in view)
    if len(data) > limit:
        return f"{hexpart} … (+{len(data) - limit} bytes)"
    return hexpart


def _force_outgoing_frame_debug_log(
    command: str,
    client_id: str,
    payload: bytes,
) -> None:
    """
    Emit outgoing-frame diagnostics even if the logger is not set to DEBUG.

    We print to stderr as a last resort because, during real-player debugging,
    we must capture TX frames to understand protocol expectations.
    """
    if not OUTGOING_FRAME_DEBUG:
        return

    try:
        prefix = "[TX]"
        print(
            f"{prefix} to={client_id} cmd={command} payload_len={len(payload)} payload_hex={_hexdump(payload)}",
            file=__import__("sys").stderr,
        )

        if command == "strm" and len(payload) >= 24:
            fixed = payload[:24]
            try:
                cmd_ch = fixed[0:1].decode("ascii", errors="replace")
                autostart_ch = fixed[1:2].decode("ascii", errors="replace")
                format_ch = fixed[2:3].decode("ascii", errors="replace")
            except Exception:
                cmd_ch = "?"
                autostart_ch = "?"
                format_ch = "?"
            server_port = struct.unpack(">H", fixed[18:20])[0]
            server_ip = struct.unpack(">I", fixed[20:24])[0]
            print(
                f"{prefix} strm parsed: command={cmd_ch} autostart={autostart_ch} format={format_ch} server_port={server_port} server_ip=0x{server_ip:08x}",
                file=__import__("sys").stderr,
            )

            if len(payload) > 24:
                req_preview = payload[24 : 24 + 200]
                print(
                    f"{prefix} strm request_preview={req_preview.decode('latin-1', errors='replace')!r}",
                    file=__import__("sys").stderr,
                )
    except Exception:
        # Never let diagnostics break protocol sending paths.
        return


# Default Slimproto port
SLIMPROTO_PORT = 3483

# Time after which a client is considered dead if no heartbeat received.
CLIENT_TIMEOUT_SECONDS = 60

# Interval for sending server heartbeats (strm t) to players
SERVER_HEARTBEAT_INTERVAL_SECONDS = 10

# How often to check for dead clients
CLIENT_CHECK_INTERVAL_SECONDS = 5

# Device ID to name mapping (from original Slimproto.pm)
DEVICE_IDS: dict[int, str] = {
    2: "squeezebox",
    3: "softsqueeze",
    4: "squeezebox2",
    5: "transporter",
    6: "softsqueeze3",
    7: "receiver",
    8: "squeezeslave",
    9: "controller",
    10: "boom",
    11: "softboom",
    12: "squeezeplay",
}

# Message handler type
MessageHandler = Callable[[PlayerClient, bytes], Coroutine[Any, Any, None]]


class SlimprotoError(Exception):
    """Base exception for Slimproto protocol errors."""

    pass


class ProtocolError(SlimprotoError):
    """Invalid protocol data received."""

    pass


class SlimprotoServer:
    """
    Slimproto protocol server for Squeezebox player communication.

    This server listens for incoming connections from Squeezebox hardware
    and software players (like Squeezelite) and handles the binary protocol
    for playback control, status updates, and other operations.

    The server is fully asynchronous using asyncio and can handle multiple
    concurrent player connections.

    Optional integration:
        streaming_server: Optional StreamingServer-like object, set by the main
            server, used to read the current per-player stream generation for
            generation-aware "track finished" (STMd) handling. This attribute is
            optional to keep the protocol layer decoupled from streaming.

    Attributes:
        host: The host address to bind to.
        port: The TCP port to listen on (default 3483).
        player_registry: Registry for tracking connected players.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = SLIMPROTO_PORT,
        streaming_port: int = 9000,
        player_registry: PlayerRegistry | None = None,
    ) -> None:
        """
        Initialize the Slimproto server.

        Args:
            host: Host address to bind to.
            port: TCP port to listen on.
            streaming_port: HTTP port for audio streaming.
            player_registry: Registry for player management (created if not provided).
        """
        self.host = host
        self.port = port
        self.streaming_port = streaming_port
        self.player_registry = player_registry if player_registry is not None else PlayerRegistry()

        # Optional: wired by the main server. Kept as `Any` to avoid a hard dependency
        # on the streaming package from the protocol layer.
        self.streaming_server: Any | None = None

        self._server: asyncio.Server | None = None
        self._running = False
        self._client_tasks: dict[str, asyncio.Task[None]] = {}
        self._heartbeat_task: asyncio.Task[None] | None = None

        # Message handlers indexed by 4-byte command
        self._handlers: dict[str, MessageHandler] = {
            "STAT": self._handle_stat,
            "BYE!": self._handle_bye,
            "IR  ": self._handle_ir,
            "RESP": self._handle_resp,
            "META": self._handle_meta,
            "DSCO": self._handle_dsco,
            "BUTN": self._handle_butn,
            "KNOB": self._handle_knob,
            "SETD": self._handle_setd,
            "ANIC": self._handle_anic,
        }

    async def start(self) -> None:
        """Start the Slimproto server and begin accepting connections."""
        if self._running:
            logger.warning("Slimproto server already running")
            return

        self._server = await asyncio.start_server(
            self._handle_connection,
            host=self.host,
            port=self.port,
            reuse_address=True,
        )

        self._running = True

        # Start heartbeat checker
        self._heartbeat_task = asyncio.create_task(self._check_heartbeats())

        logger.info("Slimproto server listening on %s:%d", self.host, self.port)

    def get_advertise_ip_for_player(self, player: PlayerClient) -> int:
        """
        Compute the IPv4 address we should advertise in 'strm' frames.

        Why:
        - Advertising 0.0.0.0 makes players try to connect to "server 0" and fail.
        - Binding to 0.0.0.0 is fine, but the advertised address must be reachable
          from the player.

        Rules:
        1) If bound host is a concrete IPv4 address (not 0.0.0.0), advertise that.
        2) If the player is connected via loopback, advertise 127.0.0.1.
        3) Otherwise, derive the local interface address used to reach the player's
           remote address (peer-facing local IP) and advertise that.

        Returns:
            IPv4 address as big-endian u32 suitable for the slimproto 'strm' header.
        """
        # 1) If host is a concrete IPv4 address, prefer it.
        try:
            host_ip = ipaddress.ip_address(self.host)
            if isinstance(host_ip, ipaddress.IPv4Address) and str(host_ip) != "0.0.0.0":
                return int(host_ip)
        except ValueError:
            # host might be a hostname; ignore and fall back
            pass

        # Determine peer IP.
        peer_ip = player.ip_address

        # 2) Loopback player => advertise loopback.
        if peer_ip in ("127.0.0.1", "::1"):
            return int(ipaddress.IPv4Address("127.0.0.1"))

        # 3) Best-effort: derive local interface IP used for this peer.
        if peer_ip and peer_ip != "unknown":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    # Port doesn't matter for UDP connect; no packets are sent.
                    s.connect((peer_ip, 9))
                    local_ip = s.getsockname()[0]
                finally:
                    s.close()

                return int(ipaddress.IPv4Address(local_ip))
            except Exception:
                pass

        # Final fallback: loopback (better than 0.0.0.0).
        return int(ipaddress.IPv4Address("127.0.0.1"))

    async def stop(self) -> None:
        """Stop the server and close all connections."""
        if not self._running:
            return

        logger.info("Stopping Slimproto server...")
        self._running = False

        # Stop heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        # Cancel all client handler tasks
        for task in self._client_tasks.values():
            task.cancel()

        if self._client_tasks:
            await asyncio.gather(*self._client_tasks.values(), return_exceptions=True)
            self._client_tasks.clear()

        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        logger.info("Slimproto server stopped")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle a new incoming connection.

        This is called by asyncio for each new client connection.
        We wait for a HELO message to identify the player, then
        process messages in a loop until disconnection.
        """
        peername = writer.get_extra_info("peername")
        remote_addr = f"{peername[0]}:{peername[1]}" if peername else "unknown"

        logger.info("New connection from %s", remote_addr)

        # Create a temporary client object for the connection
        client = PlayerClient(reader, writer)

        try:
            # First message must be HELO
            await self._wait_for_helo(client, reader)

            if client.id:
                # Register the client and start message loop
                await self.player_registry.register(client)
                if task := asyncio.current_task():
                    self._client_tasks[client.id] = task

                # Publish connect event for Cometd subscribers
                await event_bus.publish(
                    PlayerConnectedEvent(
                        player_id=client.mac_address,
                        name=client.name,
                        model=client.device_type,
                    )
                )

                # Main message processing loop
                await self._message_loop(client, reader)
        except asyncio.CancelledError:
            logger.debug("Connection handler cancelled for %s", remote_addr)
        except ConnectionResetError:
            logger.info("Connection reset by %s", remote_addr)
        except ProtocolError as e:
            logger.warning("Protocol error from %s: %s", remote_addr, e)
        except Exception as e:
            logger.exception("Error handling connection from %s: %s", remote_addr, e)
        finally:
            # Clean up
            if client.id:
                self._client_tasks.pop(client.id, None)
                await self.player_registry.unregister(client.id)

                # Publish disconnect event for Cometd subscribers
                await event_bus.publish(PlayerDisconnectedEvent(player_id=client.mac_address))

            await client.disconnect()
            logger.info("Connection closed: %s", remote_addr)

    async def _wait_for_helo(
        self,
        client: PlayerClient,
        reader: asyncio.StreamReader,
    ) -> None:
        """
        Wait for and process the initial HELO message.

        The first message from a player must be HELO, which contains
        device identification and capabilities.

        Raises:
            ProtocolError: If HELO is not received or is malformed.
            asyncio.TimeoutError: If no HELO received within timeout.
        """
        try:
            # Wait for HELO with timeout
            command, payload = await asyncio.wait_for(
                self._read_message(reader),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            raise ProtocolError("Timeout waiting for HELO") from None

        if command != "HELO":
            raise ProtocolError(f"Expected HELO, got {command}")

        self._parse_helo(client, payload)

        logger.info(
            "Player connected: %s (%s, rev %s)",
            client.id,
            client.info.device_type.name,
            client.info.firmware_version,
        )

        # Send initial server greeting/acknowledgment
        await self._send_server_capabilities(client)

    def _parse_helo(self, client: PlayerClient, data: bytes) -> None:
        """
        Parse HELO message payload and populate client info.

        HELO format (minimum 20 bytes, up to 36+ with UUID):
            [1] Device ID
            [1] Firmware revision
            [6] MAC address
            [16] UUID (optional, newer players)
            [2] WLAN channel list / flags
            [4] Bytes received high
            [4] Bytes received low
            [2] Language code
            [*] Capabilities string (optional)
        """
        if len(data) < 10:
            raise ProtocolError(f"HELO too short: {len(data)} bytes")

        # Parse fixed fields
        device_id = data[0]
        revision = data[1]

        # MAC address (bytes 2-7)
        mac_bytes = data[2:8]
        mac_address = ":".join(f"{b:02x}" for b in mac_bytes)

        # Check for UUID (36+ bytes means UUID is present)
        uuid = ""
        capabilities_offset = 20

        if len(data) >= 36:
            # UUID is 16 bytes as hex string (32 chars when parsed)
            uuid_bytes = data[8:24]
            uuid = uuid_bytes.hex()
            capabilities_offset = 36

        # Parse capabilities string if present
        capabilities: dict[str, str] = {}
        if len(data) > capabilities_offset:
            try:
                cap_string = data[capabilities_offset:].decode("utf-8", errors="ignore")
                capabilities = self._parse_capabilities(cap_string)
            except Exception as e:
                logger.debug("Failed to parse capabilities: %s", e)

        # Populate client info
        client.id = mac_address
        client.info.mac_address = mac_address
        client.info.device_type = DeviceType.from_id(device_id)
        client.info.firmware_version = str(revision)
        client.info.uuid = uuid
        client.info.capabilities = capabilities
        client.info.model = DEVICE_IDS.get(device_id, f"unknown-{device_id}")

        # Extract name from capabilities if present
        if "Name" in capabilities:
            client.info.name = capabilities["Name"]

        # Set connected state
        client.status.state = PlayerState.CONNECTED
        client.update_last_seen()

    def _parse_capabilities(self, cap_string: str) -> dict[str, str]:
        """
        Parse the capabilities string from HELO.

        Format: "Key1=Value1,Key2=Value2,..."
        """
        capabilities: dict[str, str] = {}

        for part in cap_string.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                capabilities[key.strip()] = value.strip()
            elif part.strip():
                # Flag without value
                capabilities[part.strip()] = "1"

        return capabilities

    async def _send_server_capabilities(self, client: PlayerClient) -> None:
        """Send server capabilities/acknowledgment to client after HELO."""
        logger.debug("Sending server capabilities to %s", client.id)

        # Send 'vers' frame with server version - this tells the player
        # that it's connected to a real server
        version = b"8.5.0"  # Pretend to be LMS 8.5.0
        await self._send_message(client, "vers", version)
        logger.debug("Sent vers frame to %s", client.id)

        # Also send 'setd' with player ID to confirm registration
        # Format: 1 byte ID type (0 = player ID) + player name
        setd_payload = b"\x00" + client.id.encode("ascii")
        await self._send_message(client, "setd", setd_payload)
        logger.debug("Sent setd frame to %s", client.id)

        # Send strm 't' (status request) to trigger player heartbeats
        # This is required for Squeezelite/Squeezebox2 to start sending STAT messages
        from resonance.protocol.commands import build_stream_status

        advertise_ip = self.get_advertise_ip_for_player(client)
        strm_status = build_stream_status(server_port=self.streaming_port, server_ip=advertise_ip)
        await self._send_message(client, "strm", strm_status)
        logger.debug("Sent strm status request to %s", client.id)

    async def _message_loop(
        self,
        client: PlayerClient,
        reader: asyncio.StreamReader,
    ) -> None:
        """
        Main message processing loop for a connected client.

        Reads and dispatches messages until the connection is closed.
        """
        while self._running and client.is_connected:
            try:
                command, payload = await self._read_message(reader)
            except asyncio.IncompleteReadError:
                logger.debug("Client %s disconnected (incomplete read)", client.id)
                break
            except ConnectionResetError:
                logger.debug("Client %s connection reset", client.id)
                break

            client.update_last_seen()

            # Dispatch to handler
            handler = self._handlers.get(command)
            if handler:
                try:
                    await handler(client, payload)
                except Exception as e:
                    logger.error(
                        "Error handling %s from %s: %s",
                        command,
                        client.id,
                        e,
                    )
            else:
                logger.debug("Unknown command from %s: %s", client.id, command)

    async def _read_message(
        self,
        reader: asyncio.StreamReader,
    ) -> tuple[str, bytes]:
        """
        Read a single Slimproto message from the stream.

        Returns:
            Tuple of (command, payload) where command is a 4-char string.

        Raises:
            asyncio.IncompleteReadError: If connection closed mid-message.
            ProtocolError: If message format is invalid.
        """
        # Read header: 4 bytes command + 4 bytes length
        header = await reader.readexactly(8)

        command = header[:4].decode("ascii", errors="replace")
        length = struct.unpack(">I", header[4:8])[0]

        # Sanity check on length
        if length > 65536:  # 64KB max payload
            raise ProtocolError(f"Message too large: {length} bytes")

        # Read payload
        if length > 0:
            payload = await reader.readexactly(length)
        else:
            payload = b""

        logger.debug("Received %s from client (%d bytes)", command, length)

        return command, payload

    async def _check_heartbeats(self) -> None:
        """
        Periodically check for clients that haven't sent heartbeats.

        Clients that haven't been heard from in CLIENT_TIMEOUT_SECONDS
        are considered dead and disconnected.
        """
        while self._running:
            await asyncio.sleep(CLIENT_CHECK_INTERVAL_SECONDS)

            players = await self.player_registry.get_all()
            for player in players:
                if player.seconds_since_last_seen() > CLIENT_TIMEOUT_SECONDS:
                    logger.warning(
                        "Player %s timed out (no heartbeat for %.1f seconds)",
                        player.id,
                        player.seconds_since_last_seen(),
                    )
                    await player.disconnect()
                    await self.player_registry.unregister(player.id)
                else:
                    # Send periodic heartbeat (strm t) to keep connection alive
                    try:
                        from resonance.protocol.commands import build_stream_status

                        advertise_ip = self.get_advertise_ip_for_player(player)
                        strm_status = build_stream_status(
                            server_port=self.streaming_port, server_ip=advertise_ip
                        )
                        await self._send_message(player, "strm", strm_status)
                        logger.debug("Sent heartbeat to %s", player.id)
                    except Exception as e:
                        logger.warning("Failed to send heartbeat to %s: %s", player.id, e)

    # -------------------------------------------------------------------------
    # Message Handlers
    # -------------------------------------------------------------------------

    async def _handle_stat(self, client: PlayerClient, data: bytes) -> None:
        """
        Handle STAT (status) message from player.

        This is the heartbeat/status message sent periodically by players.
        It contains playback state, buffer fullness, elapsed time, etc.

        Format (36 bytes minimum):
            [4] Event code (e.g., 'STMt', 'STMc', etc.)
            [1] Number of CRLF in buffer
            [1] MAS initialized flags (SB1 only)
            [1] MAS mode (SB1 only)
            [4] Buffer size in bytes
            [4] Data in receive buffer
            [8] Bytes received
            [2] Signal strength
            [4] Jiffies
            [4] Output buffer size
            [4] Output buffer fullness
            [4] Elapsed seconds
            [2] Voltage (Boom only)
            [4] Elapsed milliseconds
            [4] Server timestamp
            [2] Error code
        """
        if len(data) < 36:
            logger.warning("STAT too short from %s: %d bytes", client.id, len(data))
            return

        # Parse event code (first 4 bytes)
        event_code = data[:4].decode("ascii", errors="replace")

        # Parse buffer fullness (bytes 11-15)
        buffer_fullness = struct.unpack(">I", data[11:15])[0] if len(data) >= 15 else 0

        # Parse bytes received (bytes 15-23)
        bytes_received = struct.unpack(">Q", data[15:23])[0] if len(data) >= 23 else 0

        # Parse signal strength (bytes 23-25)
        signal_strength = struct.unpack(">H", data[23:25])[0] if len(data) >= 25 else 0

        # Parse elapsed seconds (bytes 37-41)
        # Format: [25-28] Jiffies, [29-32] Output buffer size, [33-36] Output buffer fullness, [37-40] Elapsed seconds
        elapsed_seconds = struct.unpack(">I", data[37:41])[0] if len(data) >= 41 else 0

        # Parse elapsed milliseconds (bytes 43-47, if present)
        # Format: [41-42] Voltage (2 bytes), [43-46] Elapsed milliseconds
        elapsed_ms = 0
        if len(data) >= 47:
            elapsed_ms = struct.unpack(">I", data[43:47])[0]

        # Update client status
        client.status.buffer_fullness = buffer_fullness
        client.status.signal_strength = signal_strength
        client.status.elapsed_seconds = elapsed_seconds
        client.status.elapsed_milliseconds = elapsed_ms

        # Update player state based on event code
        if event_code.startswith("STM"):
            state_code = event_code[3] if len(event_code) > 3 else ""
            if state_code == "p":  # Paused
                client.status.state = PlayerState.PAUSED
            elif state_code == "r":  # Playing/resumed
                client.status.state = PlayerState.PLAYING
            elif state_code == "s":  # Stopped
                client.status.state = PlayerState.STOPPED
            elif state_code == "t":  # Timer/heartbeat
                # If buffer has data and we're not already PLAYING/PAUSED, set to PLAYING
                # This fixes the case where start_stream() was called but no STMr was received
                if buffer_fullness > 0 and client.status.state not in (
                    PlayerState.PLAYING,
                    PlayerState.PAUSED,
                ):
                    logger.debug(
                        "STMt with buffer data (%d) - setting state to PLAYING",
                        buffer_fullness,
                    )
                    client.status.state = PlayerState.PLAYING

        logger.debug(
            "STAT %s from %s: buffer=%d, elapsed=%ds",
            event_code,
            client.id,
            buffer_fullness,
            elapsed_seconds,
        )

        # Fire PlayerTrackFinishedEvent on STMd (DECODE_READY):
        # This means the decoder has no more data to decode - the track is finished.
        # For HTTP streaming with Squeezelite, this is commonly the end-of-track signal.
        #
        # IMPORTANT: Some clients can emit STMd immediately on early stream disconnect / startup hiccups.
        # If we treat that as "finished", we can incorrectly auto-advance to track +1 right after
        # the user clicks play. To avoid this, require at least some playback progress.
        if event_code == "STMd":
            # Guard: ignore "finished" when the player reports no playback progress.
            # Be robust when elapsed_ms is missing/None: elapsed_seconds==0 is already enough
            # to consider this a startup hiccup rather than a real track completion.
            no_progress_seconds = (elapsed_seconds is None) or (elapsed_seconds <= 0)
            no_progress_ms = (elapsed_ms is None) or (elapsed_ms <= 0)

            if no_progress_seconds and no_progress_ms:
                logger.info(
                    "Ignoring STMd from player %s (no playback progress: elapsed=%ss/%sms)",
                    client.mac_address,
                    elapsed_seconds,
                    elapsed_ms,
                )
                return

            logger.info(
                "Track finished (STMd) from player %s - advancing playlist", client.mac_address
            )

            # Attach current streaming generation so consumers can ignore stale STMd events
            # that arrive after a manual track switch / stream cancellation.
            stream_generation = None
            try:
                streaming_server = getattr(self, "streaming_server", None)
                if streaming_server is not None:
                    stream_generation = getattr(streaming_server, "_stream_generation", {}).get(
                        client.mac_address
                    )
            except Exception:
                stream_generation = None

            event_bus.publish_sync(
                PlayerTrackFinishedEvent(
                    player_id=client.mac_address,
                    stream_generation=stream_generation,
                )
            )

        # Publish status event for Cometd subscribers
        # Only publish on significant state changes or periodically
        if event_code.startswith("STM") and event_code[3:4] in ("p", "r", "s"):
            event_bus.publish_sync(
                PlayerStatusEvent(
                    player_id=client.mac_address,
                    state=client.status.state.value,
                    volume=client.status.volume,
                    muted=client.status.muted,
                    elapsed_seconds=elapsed_seconds,
                    elapsed_milliseconds=elapsed_ms,
                )
            )

    async def _handle_bye(self, client: PlayerClient, data: bytes) -> None:
        """Handle BYE! message - player is disconnecting."""
        logger.info("Player %s sent BYE!", client.id)
        client.status.state = PlayerState.DISCONNECTED

        # Publish disconnect event
        await event_bus.publish(PlayerDisconnectedEvent(player_id=client.mac_address))

    async def _handle_ir(self, client: PlayerClient, data: bytes) -> None:
        """
        Handle IR (infrared remote) message.

        Format:
            [4] Time since startup in ticks (1KHz)
            [1] Code format
            [1] Number of bits
            [4] IR code (up to 32 bits)
        """
        if len(data) < 10:
            return

        ir_time = struct.unpack(">I", data[:4])[0]
        ir_code = data[6:10].hex()

        logger.debug("IR from %s: code=%s, time=%d", client.id, ir_code, ir_time)

        # TODO: Dispatch IR code to input handler

    async def _handle_resp(self, client: PlayerClient, data: bytes) -> None:
        """Handle RESP message - HTTP response headers from player."""
        logger.debug("RESP from %s: %d bytes", client.id, len(data))
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("RESP headers:\n%s", data.decode("latin-1", errors="replace"))

        # TODO: Process HTTP response for streaming

    async def _handle_meta(self, client: PlayerClient, data: bytes) -> None:
        """Handle META message - stream metadata from player."""
        logger.debug("META from %s: %d bytes", client.id, len(data))
        # TODO: Process stream metadata (ICY title, etc.)

    async def _handle_dsco(self, client: PlayerClient, data: bytes) -> None:
        """Handle DSCO message - player's data stream disconnected."""
        logger.debug("DSCO from %s", client.id)
        # TODO: Handle stream disconnection

    async def _handle_butn(self, client: PlayerClient, data: bytes) -> None:
        """Handle BUTN message - hardware button press."""
        logger.debug("BUTN from %s: %d bytes", client.id, len(data))
        # TODO: Process button press

    async def _handle_knob(self, client: PlayerClient, data: bytes) -> None:
        """Handle KNOB message - rotary encoder input."""
        logger.debug("KNOB from %s: %d bytes", client.id, len(data))
        # TODO: Process knob rotation

    async def _handle_setd(self, client: PlayerClient, data: bytes) -> None:
        """Handle SETD message - player settings/preferences."""
        logger.debug("SETD from %s: %d bytes", client.id, len(data))
        # TODO: Process settings update

    async def _handle_anic(self, client: PlayerClient, data: bytes) -> None:
        """Handle ANIC message - animation complete."""
        logger.debug("ANIC from %s", client.id)
        # TODO: Process animation completion

    # -------------------------------------------------------------------------
    # Stream Control Commands
    # -------------------------------------------------------------------------

    async def stream_start(
        self,
        player_id: str,
        stream_url: str | None = None,
        server_port: int = 9000,
        format: AudioFormat = AudioFormat.MP3,
        autostart: AutostartMode = AutostartMode.AUTO,
        buffer_threshold_kb: int = 255,
    ) -> bool:
        """
        Start streaming audio to a player.

        This sends a 'strm' command with 's' (start) to tell the player
        to connect back to the server and start playing audio.

        Args:
            player_id: MAC address of the target player.
            stream_url: Optional custom URL. If not provided, uses default
                        stream endpoint with player MAC.
            server_port: HTTP port the player should connect to for streaming.
            format: Audio format (MP3, FLAC, etc.).
            autostart: When to start playback.
            buffer_threshold_kb: Buffer size in KB before playback starts.

        Returns:
            True if command was sent, False if player not found.
        """
        player = await self.player_registry.get_by_mac(player_id)
        if not player:
            logger.warning("Cannot start stream: player %s not found", player_id)
            return False

        # Build the HTTP request string
        if stream_url:
            request_string = f"GET {stream_url} HTTP/1.0\r\n\r\n"
        else:
            request_string = f"GET /stream.mp3?player={player_id} HTTP/1.0\r\n\r\n"

        # IMPORTANT:
        # Do NOT advertise server_ip=0 (0.0.0.0) here.
        # A player will interpret that as "connect to server 0" and fail.
        #
        # Instead, advertise a reachable IP:
        # - If the player is local/loopback, use 127.0.0.1
        # - Otherwise, use the bound host unless it's 0.0.0.0, in which case
        #   fall back to the peer-facing local interface IP for this connection.
        #
        # Note: binding to 0.0.0.0 is fine; advertising it is not.
        advertise_ip = self.get_advertise_ip_for_player(player)

        params = StreamParams(
            format=format,
            autostart=autostart,
            buffer_threshold_kb=buffer_threshold_kb,
            server_port=server_port,
            server_ip=advertise_ip,
        )

        frame = build_strm_frame(params, request_string)

        logger.info(
            "Starting stream for player %s (port=%d, format=%s)",
            player_id,
            server_port,
            format.name,
        )
        await self._send_message(player, "strm", frame)
        return True

    async def stream_pause(self, player_id: str) -> bool:
        """
        Pause playback on a player.

        Args:
            player_id: MAC address of the target player.

        Returns:
            True if command was sent, False if player not found.
        """
        player = await self.player_registry.get_by_mac(player_id)
        if not player:
            return False

        frame = build_stream_pause()
        logger.info("Pausing stream for player %s", player_id)
        await self._send_message(player, "strm", frame)
        return True

    async def stream_unpause(self, player_id: str) -> bool:
        """
        Resume playback on a player.

        Args:
            player_id: MAC address of the target player.

        Returns:
            True if command was sent, False if player not found.
        """
        player = await self.player_registry.get_by_mac(player_id)
        if not player:
            return False

        frame = build_stream_unpause()
        logger.info("Resuming stream for player %s", player_id)
        await self._send_message(player, "strm", frame)
        return True

    async def stream_stop(self, player_id: str) -> bool:
        """
        Stop playback on a player.

        Args:
            player_id: MAC address of the target player.

        Returns:
            True if command was sent, False if player not found.
        """
        player = await self.player_registry.get_by_mac(player_id)
        if not player:
            return False

        frame = build_stream_stop()
        logger.info("Stopping stream for player %s", player_id)
        await self._send_message(player, "strm", frame)
        return True

    async def set_volume(
        self,
        player_id: str,
        volume: int,
        muted: bool = False,
    ) -> bool:
        """
        Set the volume on a player.

        Args:
            player_id: MAC address of the target player.
            volume: Volume level 0-100.
            muted: Whether to mute the player.

        Returns:
            True if command was sent, False if player not found.
        """
        player = await self.player_registry.get_by_mac(player_id)
        if not player:
            return False

        frame = build_volume_frame(volume, muted)
        logger.info(
            "Setting volume for player %s: %d%s", player_id, volume, " (muted)" if muted else ""
        )
        await self._send_message(player, "audg", frame)

        # Update local state
        player.status.volume = volume
        player.status.muted = muted
        return True

    # -------------------------------------------------------------------------
    # Server Commands (sending to players)
    # -------------------------------------------------------------------------

    async def send_to_player(
        self,
        player_id: str,
        command: str,
        payload: bytes = b"",
    ) -> bool:
        """
        Send a command to a specific player.

        Args:
            player_id: MAC address of the target player.
            command: 4-character command code.
            payload: Command payload data.

        Returns:
            True if message was sent, False if player not found.
        """
        player = await self.player_registry.get_by_mac(player_id)
        if not player:
            return False

        await self._send_message(player, command, payload)
        return True

    async def _send_message(
        self,
        client: PlayerClient,
        command: str,
        payload: bytes = b"",
    ) -> None:
        """
        Send a message to a player.

        Args:
            client: Target player client.
            command: 4-character command code.
            payload: Command payload data.
        """
        if len(command) != 4:
            raise ValueError(f"Command must be 4 characters: {command}")

        # Always emit a fallback diagnostic line (stderr) so we can see TX frames
        # even when logging configuration doesn't show DEBUG output.
        _force_outgoing_frame_debug_log(command, client.id, payload)

        if OUTGOING_FRAME_DEBUG and logger.isEnabledFor(logging.DEBUG):
            # We don't know the on-wire framing here (it depends on the player implementation),
            # but we can still log command + payload information deterministically.
            logger.debug(
                "TX to %s cmd=%s payload_len=%d payload_hex=%s",
                client.id,
                command,
                len(payload),
                _hexdump(payload),
            )

            # Special-case: show likely strm header fields when present (first 24 bytes).
            if command == "strm" and len(payload) >= 24:
                fixed = payload[:24]
                # Bytes 0..6 are ASCII-ish fields in many implementations.
                try:
                    cmd_ch = fixed[0:1].decode("ascii", errors="replace")
                    autostart_ch = fixed[1:2].decode("ascii", errors="replace")
                    format_ch = fixed[2:3].decode("ascii", errors="replace")
                except Exception:
                    cmd_ch = "?"
                    autostart_ch = "?"
                    format_ch = "?"
                server_port = struct.unpack(">H", fixed[18:20])[0]
                server_ip = struct.unpack(">I", fixed[20:24])[0]
                logger.debug(
                    "TX strm parsed: command=%s autostart=%s format=%s server_port=%d server_ip=0x%08x",
                    cmd_ch,
                    autostart_ch,
                    format_ch,
                    server_port,
                    server_ip,
                )

                if len(payload) > 24:
                    req_preview = payload[24 : 24 + 200]
                    logger.debug(
                        "TX strm request_preview=%r",
                        req_preview.decode("latin-1", errors="replace"),
                    )

        await client.send_message(command.encode("ascii"), payload)

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._running
