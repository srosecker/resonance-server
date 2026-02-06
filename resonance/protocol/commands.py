"""
Slimproto commands for Server → Player communication.

This module implements the binary command frames that the server sends
to Squeezebox players. The most important command is 'strm' which controls
audio streaming.

Reference: Slim/Player/Squeezebox.pm from the original LMS
"""

import struct
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class StreamCommand(Enum):
    """Stream command types for the 'strm' frame."""

    START = ord("s")  # Start streaming
    PAUSE = ord("p")  # Pause playback
    UNPAUSE = ord("u")  # Resume playback
    STOP = ord("q")  # Stop playback (quit)
    FLUSH = ord("f")  # Flush buffer
    STATUS = ord("t")  # Request status
    SKIP = ord("a")  # Skip ahead (autostart at position)


class AutostartMode(Enum):
    """Autostart modes for stream command."""

    OFF = ord("0")  # Don't auto-start
    AUTO = ord("1")  # Auto-start when buffer ready
    DIRECT = ord("2")  # Direct streaming, no auto-start
    DIRECT_AUTO = ord("3")  # Direct streaming with auto-start


class AudioFormat(Enum):
    """Audio format byte for stream command."""

    MP3 = ord("m")  # MP3 bitstream
    PCM = ord("p")  # PCM audio
    FLAC = ord("f")  # FLAC
    OGG = ord("o")  # Ogg Vorbis
    AAC = ord("a")  # AAC
    WMA = ord("w")  # WMA
    ALAC = ord("l")  # Apple Lossless
    DSD = ord("d")  # DSD
    UNKNOWN = ord("?")  # Unknown/don't care


class PCMSampleSize(Enum):
    """PCM sample size options."""

    BITS_8 = ord("0")
    BITS_16 = ord("1")
    BITS_24 = ord("2")
    BITS_32 = ord("3")

    # AAC container types (reused field when format is AAC)
    # '1' (adif), '2' (adts), '3' (latm within loas),
    # '4' (rawpkts), '5' (mp4ff), '6' (latm within rawpkts)
    AAC_ADIF = ord("1")
    AAC_ADTS = ord("2")
    AAC_LATM_LOAS = ord("3")
    AAC_RAWPKTS = ord("4")
    AAC_MP4FF = ord("5")
    AAC_LATM_RAWPKTS = ord("6")

    SELF_DESCRIBING = ord("?")  # Let decoder figure it out


class PCMSampleRate(Enum):
    """PCM sample rate options."""

    RATE_11000 = ord("0")
    RATE_22000 = ord("1")
    RATE_32000 = ord("2")
    RATE_44100 = ord("3")
    RATE_48000 = ord("4")
    RATE_8000 = ord("5")
    RATE_12000 = ord("6")
    RATE_16000 = ord("7")
    RATE_24000 = ord("8")
    RATE_96000 = ord("9")
    SELF_DESCRIBING = ord("?")  # Let decoder figure it out


class PCMChannels(Enum):
    """PCM channel configuration."""

    MONO = ord("1")
    STEREO = ord("2")
    SELF_DESCRIBING = ord("?")


class PCMEndianness(Enum):
    """PCM byte order."""

    BIG = ord("0")
    LITTLE = ord("1")
    SELF_DESCRIBING = ord("?")


class TransitionType(Enum):
    """Audio transition types."""

    NONE = ord("0")
    CROSSFADE = ord("1")
    FADE_IN = ord("2")
    FADE_OUT = ord("3")
    FADE_IN_OUT = ord("4")
    CROSSFADE_IMMEDIATE = ord("5")


class SpdifMode(Enum):
    """S/PDIF output mode."""

    AUTO = 0
    ON = 1
    OFF = 2


# Flag bit constants
FLAG_LOOP_INFINITE = 0x80
FLAG_NO_RESTART_DECODER = 0x40
FLAG_USE_SSL = 0x20
FLAG_DIRECT_PROTOCOL = 0x10
FLAG_MONO_RIGHT = 0x08
FLAG_MONO_LEFT = 0x04
FLAG_INVERT_RIGHT = 0x02
FLAG_INVERT_LEFT = 0x01


@dataclass
class StreamParams:
    """Parameters for building a stream command frame."""

    command: StreamCommand = StreamCommand.START
    autostart: AutostartMode = AutostartMode.AUTO
    format: AudioFormat = AudioFormat.MP3
    pcm_sample_size: PCMSampleSize = PCMSampleSize.SELF_DESCRIBING
    pcm_sample_rate: PCMSampleRate = PCMSampleRate.SELF_DESCRIBING
    pcm_channels: PCMChannels = PCMChannels.SELF_DESCRIBING
    pcm_endianness: PCMEndianness = PCMEndianness.SELF_DESCRIBING
    buffer_threshold_kb: int = 255  # KB of buffer before autostart
    spdif_mode: SpdifMode = SpdifMode.AUTO
    transition_duration: int = 0  # Seconds
    transition_type: TransitionType = TransitionType.NONE
    flags: int = 0
    output_threshold: int = 0  # Tenths of second
    slave_streams: int = 0
    replay_gain: int = 0  # 16.16 fixed point, 0 = none
    server_port: int = 9000  # HTTP port for streaming
    server_ip: int = 0  # 0 = use control server IP


STRM_FIXED_HEADER_SIZE = 24


def build_strm_frame(params: StreamParams, request_string: str = "") -> bytes:
    """
    Build a 'strm' command frame to send to a player.

    The strm frame controls audio streaming. It tells the player what to
    stream, from where, and in what format.

    Frame layout (24 bytes fixed header + variable request string):
        offset  size  field
        0       1     command ('s', 'p', 'u', 'q', 'f', 't', 'a')
        1       1     autostart ('0', '1', '2', '3')
        2       1     format ('m', 'p', 'f', 'o', 'a', 'w', etc.)
        3       1     pcm_sample_size ('0'-'3', '?')
        4       1     pcm_sample_rate ('0'-'9', '?')
        5       1     pcm_channels ('1', '2', '?')
        6       1     pcm_endianness ('0', '1', '?')
        7       1     buffer_threshold (KB)
        8       1     spdif_enable (0, 1, 2)
        9       1     transition_duration (seconds)
        10      1     transition_type ('0'-'5')
        11      1     flags (bit field)
        12      1     output_threshold (tenths of second)
        13      1     slave_streams
        14-17   4     replay_gain (32-bit, 16.16 fixed point)
        18-19   2     server_port
        20-23   4     server_ip (0 = use control server IP)
        24+     var   request_string (HTTP request)

    Args:
        params: Stream parameters.
        request_string: HTTP request string to send to streaming server.

    Returns:
        Complete strm frame bytes.
    """
    # Pack the 24-byte fixed header
    # Format string breakdown:
    #   c c c c c c c = 7 single bytes (command through pcm_endianness)
    #   B             = unsigned byte (buffer_threshold)
    #   B             = unsigned byte (spdif)
    #   B             = unsigned byte (transition_duration)
    #   c             = single byte (transition_type)
    #   B             = unsigned byte (flags)
    #   B             = unsigned byte (output_threshold)
    #   B             = unsigned byte (slave_streams)
    #   I             = 4-byte unsigned int (replay_gain, big-endian)
    #   H             = 2-byte unsigned short (server_port, big-endian)
    #   I             = 4-byte unsigned int (server_ip, big-endian)

    frame = struct.pack(
        ">cccccccBBBcBBBIHI",
        bytes([params.command.value]),
        bytes([params.autostart.value]),
        bytes([params.format.value]),
        bytes([params.pcm_sample_size.value]),
        bytes([params.pcm_sample_rate.value]),
        bytes([params.pcm_channels.value]),
        bytes([params.pcm_endianness.value]),
        params.buffer_threshold_kb & 0xFF,
        params.spdif_mode.value,
        params.transition_duration & 0xFF,
        bytes([params.transition_type.value]),
        params.flags & 0xFF,
        params.output_threshold & 0xFF,
        params.slave_streams & 0xFF,
        params.replay_gain,
        params.server_port,
        params.server_ip,
    )

    assert len(frame) == STRM_FIXED_HEADER_SIZE, f"Header size mismatch: {len(frame)}"

    # Append the request string
    return frame + request_string.encode("latin-1")


def build_stream_start(
    player_mac: str,
    server_port: int = 9000,
    server_ip: int = 0,
    format: AudioFormat = AudioFormat.MP3,
    pcm_sample_size: PCMSampleSize = PCMSampleSize.SELF_DESCRIBING,
    pcm_sample_rate: PCMSampleRate = PCMSampleRate.SELF_DESCRIBING,
    pcm_channels: PCMChannels = PCMChannels.SELF_DESCRIBING,
    pcm_endianness: PCMEndianness = PCMEndianness.SELF_DESCRIBING,
    autostart: AutostartMode = AutostartMode.AUTO,
    buffer_threshold_kb: int = 255,
) -> bytes:
    """
    Build a strm frame to start streaming audio to a player.

    This is a convenience function for the common case of starting
    an MP3 or FLAC stream from the server.

    Args:
        player_mac: MAC address of the player (used in request URL).
        server_port: HTTP port the player should connect to.
        server_ip: Server IP (0 = use control server IP).
        format: Audio format.
        pcm_sample_size: PCM sample size (for PCM format).
        pcm_sample_rate: PCM sample rate (for PCM format).
        pcm_channels: PCM channel count (for PCM format).
        pcm_endianness: PCM byte order (for PCM format).
        autostart: Autostart mode.
        buffer_threshold_kb: Buffer threshold in KB.

    Returns:
        Complete strm frame bytes.
    """
    # Build the HTTP request the player will make to get the stream
    # The player connects back to the server to receive audio data
    request_string = f"GET /stream.mp3?player={player_mac} HTTP/1.0\r\n\r\n"

    params = StreamParams(
        command=StreamCommand.START,
        autostart=autostart,
        format=format,
        pcm_sample_size=pcm_sample_size,
        pcm_sample_rate=pcm_sample_rate,
        pcm_channels=pcm_channels,
        pcm_endianness=pcm_endianness,
        buffer_threshold_kb=buffer_threshold_kb,
        server_port=server_port,
        server_ip=server_ip,
    )

    return build_strm_frame(params, request_string)


def build_stream_pause(interval_ms: int = 0) -> bytes:
    """
    Build a strm frame to pause playback.

    Args:
        interval_ms: Optional pause-at timestamp in milliseconds.

    Returns:
        Complete strm frame bytes.
    """
    params = StreamParams(
        command=StreamCommand.PAUSE,
        autostart=AutostartMode.OFF,
        format=AudioFormat.MP3,
        replay_gain=interval_ms,  # replay_gain field used for timestamp
    )
    return build_strm_frame(params)


def build_stream_unpause(interval: int = 0) -> bytes:
    """
    Build a strm frame to resume playback.

    Args:
        interval: Optional unpause-at timestamp.

    Returns:
        Complete strm frame bytes.
    """
    params = StreamParams(
        command=StreamCommand.UNPAUSE,
        autostart=AutostartMode.OFF,
        format=AudioFormat.MP3,
        replay_gain=interval,
    )
    return build_strm_frame(params)


def build_stream_stop() -> bytes:
    """
    Build a strm frame to stop playback.

    Returns:
        Complete strm frame bytes.
    """
    params = StreamParams(
        command=StreamCommand.STOP,
        autostart=AutostartMode.OFF,
        format=AudioFormat.MP3,
    )
    return build_strm_frame(params)


def build_stream_flush() -> bytes:
    """
    Build a strm frame to flush the player's buffer.

    Returns:
        Complete strm frame bytes.
    """
    params = StreamParams(
        command=StreamCommand.FLUSH,
        autostart=AutostartMode.OFF,
        format=AudioFormat.MP3,
    )
    return build_strm_frame(params)


def build_stream_status(server_port: int = 9000, server_ip: int = 0) -> bytes:
    """
    Build a strm frame to request player status.

    This sends a 't' command which prompts the player to send
    a STAT response.

    Note:
        Some players treat server_ip=0 (0.0.0.0) as "server 0" and will log
        "unable to connect to server 0". To avoid this, callers should pass a
        reachable server_ip (e.g. 127.0.0.1 for local testing).

    Args:
        server_port: HTTP port to advertise (reserved/ignored by some clients for status).
        server_ip: IPv4 address to advertise as a 32-bit big-endian integer.

    Returns:
        Complete strm frame bytes.
    """
    params = StreamParams(
        command=StreamCommand.STATUS,
        autostart=AutostartMode.OFF,
        format=AudioFormat.MP3,
        server_port=server_port,
        server_ip=server_ip,
    )
    return build_strm_frame(params)


# ============================================================================
# Audio Gain Command (audg)
# ============================================================================


def build_audg_frame(
    left_gain: int = 128,
    right_gain: int = 128,
    preamp: int = 255,
    digital_volume: bool = True,
    seq_no: int | None = None,
) -> bytes:
    """
    Build an 'audg' frame to set player volume/gain.

    Frame layout:
        offset  size  field
        0-3     4     old_left (deprecated, set to 0)
        4-7     4     old_right (deprecated, set to 0)
        8       1     digital_volume_control (0 or 1)
        9       1     preamp (0-255)
        10-13   4     left_gain (32-bit, 16.16 fixed point)
        14-17   4     right_gain (32-bit, 16.16 fixed point)
        18-21   4     sequence_number (optional, for volume sync)

    The sequence number is used by SqueezePlay/Jive devices to track
    volume changes. When the player sends a volume change with seq_no,
    we echo it back so the player can discard stale updates.

    Args:
        left_gain: Left channel gain (0-256, 128 = unity).
        right_gain: Right channel gain (0-256, 128 = unity).
        preamp: Preamp gain (0-255).
        digital_volume: Whether to use digital volume control.
        seq_no: Sequence number from client (for volume sync).

    Returns:
        Complete audg frame bytes.
    """
    # Convert 0-256 gain to 16.16 fixed point
    # Unity gain (128) = 0x00010000
    left_fixed = (left_gain << 8) & 0xFFFFFFFF
    right_fixed = (right_gain << 8) & 0xFFFFFFFF

    frame = struct.pack(
        ">IIBBII",
        0,  # old_left (deprecated)
        0,  # old_right (deprecated)
        1 if digital_volume else 0,
        preamp,
        left_fixed,
        right_fixed,
    )

    # Append sequence number if provided (LMS compatibility)
    # This allows the player to track which volume updates are current
    if seq_no is not None:
        frame += struct.pack(">I", seq_no)

    return frame


def build_volume_frame(volume: int, muted: bool = False, seq_no: int | None = None) -> bytes:
    """
    Build an audg frame to set volume.

    This is a convenience wrapper around build_audg_frame.

    Args:
        volume: Volume level 0-100.
        muted: Whether volume should be muted.
        seq_no: Sequence number from client (for volume sync with SqueezePlay).

    Returns:
        Complete audg frame bytes.
    """
    if muted:
        gain = 0
    else:
        # Convert 0-100 to 0-256 gain
        gain = int((volume / 100) * 256)

    return build_audg_frame(left_gain=gain, right_gain=gain, seq_no=seq_no)


def build_aude_frame(spdif_enable: bool = True, dac_enable: bool = True) -> bytes:
    """
    Build an 'aude' frame to enable/disable audio outputs.

    This command controls the audio output hardware on Squeezebox players.
    Used when powering the player on/off.

    Frame layout:
        offset  size  field
        0       1     S/PDIF (digital) output enable (0=off, 1=on)
        1       1     DAC (analog) output enable (0=off, 1=on)

    Args:
        spdif_enable: Enable S/PDIF digital output.
        dac_enable: Enable DAC analog output.

    Returns:
        Complete aude frame bytes (2 bytes).
    """
    return struct.pack("BB", 1 if spdif_enable else 0, 1 if dac_enable else 0)


# ============================================================================
# Display Command (grfe/grfb/grfd)
# ============================================================================


def build_display_clear() -> bytes:
    """
    Build a 'grfe' frame to clear the player display.

    Returns:
        Complete grfe frame bytes with blank display.
    """
    # grfe frame: offset (2 bytes) + transition (1) + param (1) + bitmap data
    # For now, just send empty frame to clear
    return struct.pack(">HBB", 0, 0, 0)
