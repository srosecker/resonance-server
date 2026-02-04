"""
Player client representation for Resonance.

This module defines the PlayerClient class which represents a connected
Squeezebox player (hardware or software like Squeezelite).
"""

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asyncio import StreamReader, StreamWriter

    from resonance.core.playlist import PlaylistTrack

logger = logging.getLogger(__name__)


class PlayerState(Enum):
    """Possible states of a player."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class DeviceType(Enum):
    """Known Squeezebox device types."""

    UNKNOWN = 0
    SLIMP3 = 1
    SQUEEZEBOX = 2
    SOFTSQUEEZE = 3
    SQUEEZEBOX2 = 4
    TRANSPORTER = 5
    SOFTSQUEEZE3 = 6
    RECEIVER = 7
    SQUEEZESLAVE = 8
    CONTROLLER = 9
    BOOM = 10
    SOFTBOOM = 11
    SQUEEZEPLAY = 12

    @classmethod
    def from_id(cls, device_id: int) -> "DeviceType":
        """Get device type from numeric ID."""
        try:
            return cls(device_id)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class PlayerInfo:
    """Static information about a player, set during HELO handshake."""

    device_type: DeviceType = DeviceType.UNKNOWN
    firmware_version: str = ""
    mac_address: str = ""
    uuid: str = ""
    name: str = ""
    model: str = ""
    capabilities: dict[str, str] = field(default_factory=dict)


@dataclass
class PlayerStatus:
    """Dynamic status of a player, updated via STAT messages."""

    state: PlayerState = PlayerState.DISCONNECTED
    volume: int = 50
    muted: bool = False
    elapsed_seconds: float = 0.0
    elapsed_milliseconds: int = 0
    buffer_fullness: int = 0
    output_buffer_fullness: int = 0
    signal_strength: int = 0
    last_seen: float = field(default_factory=time.time)


class PlayerClient:
    """
    Represents a connected Squeezebox player.

    Each PlayerClient instance manages the state and communication
    with a single player device. It tracks both static information
    (set during connection) and dynamic status (updated continuously).

    Attributes:
        id: Unique identifier for this player (usually MAC address).
        info: Static player information from HELO.
        status: Dynamic player status from STAT messages.
    """

    def __init__(
        self,
        reader: "StreamReader",
        writer: "StreamWriter",
        client_id: str | None = None,
    ) -> None:
        """
        Initialize a new player client.

        Args:
            reader: Asyncio stream reader for this connection.
            writer: Asyncio stream writer for this connection.
            client_id: Optional identifier (usually set after HELO).
        """
        self._reader = reader
        self._writer = writer
        self._id = client_id or ""

        self.info = PlayerInfo()
        self.status = PlayerStatus()

        # Connection metadata
        peername = writer.get_extra_info("peername")
        self._remote_ip = peername[0] if peername else "unknown"
        self._remote_port = peername[1] if peername else 0
        self._connected_at = time.time()

        logger.debug(
            "PlayerClient created for connection from %s:%d",
            self._remote_ip,
            self._remote_port,
        )

    @property
    def id(self) -> str:
        """Get the player's unique identifier (MAC address)."""
        return self._id

    @id.setter
    def id(self, value: str) -> None:
        """Set the player's unique identifier."""
        self._id = value

    @property
    def name(self) -> str:
        """Get the player's display name."""
        return self.info.name or self._id or f"Player-{self._remote_ip}"

    @property
    def mac_address(self) -> str:
        """Get the player's MAC address."""
        return self.info.mac_address or self._id

    @property
    def ip_address(self) -> str:
        """Get the player's IP address."""
        return self._remote_ip

    @property
    def is_connected(self) -> bool:
        """Check if the player is still connected."""
        return self.status.state != PlayerState.DISCONNECTED

    @property
    def remote_address(self) -> tuple[str, int]:
        """Get the remote IP address and port."""
        return (self._remote_ip, self._remote_port)

    async def send_message(self, command: bytes, payload: bytes = b"") -> None:
        """
        Send a message to the player.

        Args:
            command: 4-byte command tag (e.g., b'strm', b'audg').
            payload: Message payload bytes.

        Raises:
            ConnectionError: If the connection is closed.
        """
        if len(command) != 4:
            raise ValueError(f"Command must be exactly 4 bytes, got {len(command)}")

        # Debug: attempt to parse outgoing STRM header even when sent directly
        # via PlayerClient (i.e., bypassing SlimprotoServer._send_message()).
        if command == b"strm" and len(payload) >= 24 and logger.isEnabledFor(logging.DEBUG):
            fixed = payload[:24]
            try:
                cmd_ch = fixed[0:1].decode("ascii", errors="replace")
                autostart_ch = fixed[1:2].decode("ascii", errors="replace")
                format_ch = fixed[2:3].decode("ascii", errors="replace")
                pcm_sample_size_ch = fixed[3:4].decode("ascii", errors="replace")
                pcm_sample_rate_ch = fixed[4:5].decode("ascii", errors="replace")
                pcm_channels_ch = fixed[5:6].decode("ascii", errors="replace")
                pcm_endian_ch = fixed[6:7].decode("ascii", errors="replace")
            except Exception:
                cmd_ch = "?"
                autostart_ch = "?"
                format_ch = "?"
                pcm_sample_size_ch = "?"
                pcm_sample_rate_ch = "?"
                pcm_channels_ch = "?"
                pcm_endian_ch = "?"
            server_port = struct.unpack(">H", fixed[18:20])[0]
            server_ip = struct.unpack(">I", fixed[20:24])[0]
            logger.debug(
                "PlayerClient TX strm parsed: command=%s autostart=%s format=%s pcm_sz=%s pcm_rate=%s pcm_ch=%s pcm_endian=%s server_port=%d server_ip=0x%08x",
                cmd_ch,
                autostart_ch,
                format_ch,
                pcm_sample_size_ch,
                pcm_sample_rate_ch,
                pcm_channels_ch,
                pcm_endian_ch,
                server_port,
                server_ip,
            )
            if len(payload) > 24:
                req_preview = payload[24 : 24 + 200]
                logger.debug(
                    "PlayerClient TX strm request_preview=%r",
                    req_preview.decode("latin-1", errors="replace"),
                )

        # Message format: [2 bytes length (len+4)][4 bytes command][payload]
        message = (len(payload) + 4).to_bytes(2, "big") + command + payload

        try:
            self._writer.write(message)
            await self._writer.drain()
            logger.debug("Sent %s to %s (%d bytes)", command, self.id, len(payload))
        except (ConnectionError, OSError) as e:
            logger.warning("Failed to send to %s: %s", self.id, e)
            await self.disconnect()
            raise ConnectionError(f"Player {self.id} disconnected: {e}") from e

    async def disconnect(self) -> None:
        """Close the connection to this player."""
        if self.status.state == PlayerState.DISCONNECTED:
            return

        logger.info("Disconnecting player %s", self.name)
        self.status.state = PlayerState.DISCONNECTED

        try:
            self._writer.close()
            await self._writer.wait_closed()
        except (ConnectionError, OSError):
            pass  # Already disconnected

    def update_last_seen(self) -> None:
        """Update the last seen timestamp."""
        self.status.last_seen = time.time()

    def seconds_since_last_seen(self) -> float:
        """Get seconds elapsed since last communication."""
        return time.time() - self.status.last_seen

    def __repr__(self) -> str:
        """Return a string representation for debugging."""
        return (
            f"PlayerClient(id={self._id!r}, name={self.name!r}, "
            f"type={self.info.device_type.name}, state={self.status.state.name})"
        )

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        return f"{self.name} ({self.info.device_type.name})"

    # =========================================================================
    # Playback Control Methods
    # =========================================================================

    @property
    def device_type(self) -> str:
        """Get the device type as a string."""
        return self.info.device_type.name.lower()

    async def play(self) -> None:
        """
        Resume playback (unpause).

        Note: To start a new stream, use start_stream() instead.
        This only resumes a paused stream.
        """
        from resonance.protocol.commands import build_stream_unpause

        logger.info("Resuming playback on %s", self.name)
        frame = build_stream_unpause()
        await self.send_message(b"strm", frame)
        self.status.state = PlayerState.PLAYING

    async def pause(self) -> None:
        """Pause playback."""
        from resonance.protocol.commands import build_stream_pause

        logger.info("Pausing playback on %s", self.name)
        frame = build_stream_pause()
        await self.send_message(b"strm", frame)
        self.status.state = PlayerState.PAUSED

    async def stop(self) -> None:
        """Stop playback and clear the buffer."""
        from resonance.protocol.commands import build_stream_stop

        logger.info("Stopping playback on %s", self.name)
        frame = build_stream_stop()
        await self.send_message(b"strm", frame)
        self.status.state = PlayerState.STOPPED

    async def flush(self) -> None:
        """Flush the player's buffer.

        This is used during track changes to immediately clear the old audio
        from the buffer, ensuring the new track starts without delay.
        LMS does this via closeStream() + flush in _stopClient().
        """
        from resonance.protocol.commands import build_stream_flush

        logger.info("Flushing buffer on %s", self.name)
        frame = build_stream_flush()
        await self.send_message(b"strm", frame)

    async def toggle_pause(self) -> None:
        """Toggle between playing and paused states."""
        if self.status.state == PlayerState.PAUSED:
            await self.play()
        elif self.status.state == PlayerState.PLAYING:
            await self.pause()
        else:
            # If stopped or other state, try to play
            await self.play()

    async def set_volume(self, volume: int, muted: bool = False) -> None:
        """
        Set the player volume.

        Args:
            volume: Volume level 0-100.
            muted: Whether to mute the player.
        """
        from resonance.protocol.commands import build_volume_frame

        volume = max(0, min(100, volume))  # Clamp to 0-100
        logger.info("Setting volume to %d%s on %s", volume, " (muted)" if muted else "", self.name)
        frame = build_volume_frame(volume, muted)
        await self.send_message(b"audg", frame)
        self.status.volume = volume
        self.status.muted = muted

    async def volume_up(self, step: int = 5) -> None:
        """Increase volume by step percent."""
        new_volume = min(100, self.status.volume + step)
        await self.set_volume(new_volume)

    async def volume_down(self, step: int = 5) -> None:
        """Decrease volume by step percent."""
        new_volume = max(0, self.status.volume - step)
        await self.set_volume(new_volume)

    async def mute(self) -> None:
        """Mute the player."""
        await self.set_volume(self.status.volume, muted=True)

    async def unmute(self) -> None:
        """Unmute the player."""
        await self.set_volume(self.status.volume, muted=False)

    # =========================================================================
    # Stream Control Methods
    # =========================================================================

    async def start_stream(
        self,
        track_path: str,
        *,
        server_port: int,
        server_ip: int,
        format_hint: str = "mp3",
        buffer_threshold_kb: int = 255,
    ) -> None:
        """
        Start streaming a track to this player.

        This sends a 'strm' start command with the appropriate HTTP request
        that tells the player where to fetch the audio data.

        Args:
            track_path: Path to the audio file (used in the stream URL).
            server_port: HTTP port the player should connect to.
            server_ip: Server IP (0 = use control server IP).
            format_hint: Audio format hint ('mp3', 'flac', 'ogg', etc.).
            buffer_threshold_kb: Player buffer threshold (KB) required before starting playback.
                Lower values start sooner (snappier track changes) but can increase underruns.
        """
        from resonance.protocol.commands import (
            AudioFormat,
            AutostartMode,
            PCMChannels,
            PCMEndianness,
            PCMSampleRate,
            PCMSampleSize,
            build_stream_start,
        )

        # Determine audio format from file extension or hint.
        #
        # IMPORTANT:
        # The HTTP streaming route may transcode certain formats on the server side.
        # The `strm` command MUST signal the format the player will actually receive.
        #
        # Source of truth:
        # - resonance.streaming.policy.strm_expected_format_hint()
        logger.debug("Resolving format for hint: %s", format_hint)

        from resonance.streaming.policy import strm_expected_format_hint

        expected_hint = strm_expected_format_hint(format_hint, self.info.device_type)
        hint_lower = expected_hint.lower()

        # If the server will transcode, expected_hint will be "flac" (current policy).
        if hint_lower == "flac":
            audio_format = AudioFormat.FLAC
            autostart = AutostartMode.AUTO
            pcm_sample_size = PCMSampleSize.SELF_DESCRIBING
            pcm_sample_rate = PCMSampleRate.SELF_DESCRIBING
            pcm_channels = PCMChannels.SELF_DESCRIBING
            pcm_endianness = PCMEndianness.SELF_DESCRIBING
            logger.debug(
                "Streaming policy expects transcoded output for hint=%s -> %s (format='f')",
                format_hint,
                expected_hint,
            )
        elif hint_lower in ("wav", "pcm"):
            audio_format = AudioFormat.PCM
            autostart = AutostartMode.AUTO
            pcm_sample_size = PCMSampleSize.SELF_DESCRIBING
            pcm_sample_rate = PCMSampleRate.SELF_DESCRIBING
            pcm_channels = PCMChannels.SELF_DESCRIBING
            pcm_endianness = PCMEndianness.SELF_DESCRIBING
        else:
            format_map = {
                "mp3": AudioFormat.MP3,
                "flac": AudioFormat.FLAC,
                "ogg": AudioFormat.OGG,
            }
            audio_format = format_map.get(hint_lower, AudioFormat.MP3)
            autostart = AutostartMode.AUTO
            pcm_sample_size = PCMSampleSize.SELF_DESCRIBING
            pcm_sample_rate = PCMSampleRate.SELF_DESCRIBING
            pcm_channels = PCMChannels.SELF_DESCRIBING
            pcm_endianness = PCMEndianness.SELF_DESCRIBING

        logger.debug(
            "start_stream logic: hint='%s' -> format=%s (val=%r), autostart=%s (val=%r), pcm_sz=%s [port=%d, ip=%d]",
            format_hint,
            audio_format.name,
            chr(audio_format.value),
            autostart.name,
            chr(autostart.value),
            chr(pcm_sample_size.value),
            server_port,
            server_ip,
        )

        logger.info(
            "Starting stream for %s on %s (format=%s, autostart=%s, port=%d)",
            track_path,
            self.name,
            audio_format.name,
            autostart.name,
            server_port,
        )

        # Build and send the strm start frame
        frame = build_stream_start(
            player_mac=self.mac_address,
            server_port=server_port,
            server_ip=server_ip,
            format=audio_format,
            pcm_sample_size=pcm_sample_size,
            pcm_sample_rate=pcm_sample_rate,
            pcm_channels=pcm_channels,
            pcm_endianness=pcm_endianness,
            autostart=autostart,
            buffer_threshold_kb=buffer_threshold_kb,
        )
        await self.send_message(b"strm", frame)
        self.status.state = PlayerState.PLAYING

    def get_streaming_url(self, server_host: str, server_port: int = 9000) -> str:
        """
        Get the streaming URL for this player.

        Args:
            server_host: Server hostname or IP.
            server_port: HTTP port.

        Returns:
            URL string the player would connect to.
        """
        return f"http://{server_host}:{server_port}/stream.mp3?player={self.mac_address}"

    async def start_track(
        self,
        track: "PlaylistTrack",
        *,
        server_port: int,
        server_ip: int,
    ) -> None:
        """
        Start playing a PlaylistTrack.

        This is a convenience method that extracts format from the track path
        and calls start_stream.

        Args:
            track: The PlaylistTrack to play.
            server_port: HTTP port for streaming.
            server_ip: Server IP (0 = use control server IP).
        """
        from pathlib import Path

        # Extract format from file extension
        path = Path(track.path)
        format_hint = path.suffix.lstrip(".").lower() or "mp3"

        await self.start_stream(
            track.path,
            server_port=server_port,
            server_ip=server_ip,
            format_hint=format_hint,
        )
