"""
Unit tests for Slimproto commands (Server → Player).

Tests the binary command frame builders for strm, audg, and other
commands that the server sends to players.
"""

import struct

import pytest

from resonance.protocol.commands import (
    STRM_FIXED_HEADER_SIZE,
    AudioFormat,
    AutostartMode,
    PCMChannels,
    PCMEndianness,
    PCMSampleRate,
    PCMSampleSize,
    SpdifMode,
    StreamCommand,
    StreamParams,
    TransitionType,
    build_audg_frame,
    build_stream_flush,
    build_stream_pause,
    build_stream_start,
    build_stream_status,
    build_stream_stop,
    build_stream_unpause,
    build_strm_frame,
    build_volume_frame,
)


class TestStreamParams:
    """Tests for StreamParams dataclass."""

    def test_default_values(self) -> None:
        """Default StreamParams should have sensible values."""
        params = StreamParams()

        assert params.command == StreamCommand.START
        assert params.autostart == AutostartMode.AUTO
        assert params.format == AudioFormat.MP3
        assert params.buffer_threshold_kb == 255
        assert params.server_ip == 0

    def test_custom_values(self) -> None:
        """StreamParams should accept custom values."""
        params = StreamParams(
            command=StreamCommand.PAUSE,
            format=AudioFormat.FLAC,
            server_port=8080,
        )

        assert params.command == StreamCommand.PAUSE
        assert params.format == AudioFormat.FLAC
        assert params.server_port == 8080


class TestBuildStrmFrame:
    """Tests for build_strm_frame function."""

    def test_header_size(self) -> None:
        """Frame without request string should be exactly 24 bytes."""
        params = StreamParams()
        frame = build_strm_frame(params, "")

        assert len(frame) == STRM_FIXED_HEADER_SIZE

    def test_header_with_request_string(self) -> None:
        """Frame with request string should be 24 + len(request)."""
        params = StreamParams()
        request = "GET /stream.mp3 HTTP/1.0\r\n\r\n"
        frame = build_strm_frame(params, request)

        assert len(frame) == STRM_FIXED_HEADER_SIZE + len(request)

    def test_command_byte(self) -> None:
        """First byte should be the command character."""
        params = StreamParams(command=StreamCommand.START)
        frame = build_strm_frame(params, "")

        assert frame[0:1] == b"s"

        params = StreamParams(command=StreamCommand.PAUSE)
        frame = build_strm_frame(params, "")

        assert frame[0:1] == b"p"

        params = StreamParams(command=StreamCommand.STOP)
        frame = build_strm_frame(params, "")

        assert frame[0:1] == b"q"

    def test_autostart_byte(self) -> None:
        """Second byte should be the autostart mode."""
        params = StreamParams(autostart=AutostartMode.AUTO)
        frame = build_strm_frame(params, "")

        assert frame[1:2] == b"1"

        params = StreamParams(autostart=AutostartMode.OFF)
        frame = build_strm_frame(params, "")

        assert frame[1:2] == b"0"

        params = StreamParams(autostart=AutostartMode.DIRECT_AUTO)
        frame = build_strm_frame(params, "")

        assert frame[1:2] == b"3"

    def test_format_byte(self) -> None:
        """Third byte should be the format character."""
        params = StreamParams(format=AudioFormat.MP3)
        frame = build_strm_frame(params, "")

        assert frame[2:3] == b"m"

        params = StreamParams(format=AudioFormat.FLAC)
        frame = build_strm_frame(params, "")

        assert frame[2:3] == b"f"

        params = StreamParams(format=AudioFormat.PCM)
        frame = build_strm_frame(params, "")

        assert frame[2:3] == b"p"

    def test_server_port_position(self) -> None:
        """Server port should be at bytes 18-19 (big-endian)."""
        params = StreamParams(server_port=9000)
        frame = build_strm_frame(params, "")

        port = struct.unpack(">H", frame[18:20])[0]
        assert port == 9000

        params = StreamParams(server_port=8080)
        frame = build_strm_frame(params, "")

        port = struct.unpack(">H", frame[18:20])[0]
        assert port == 8080

    def test_server_ip_position(self) -> None:
        """Server IP should be at bytes 20-23 (big-endian)."""
        params = StreamParams(server_ip=0)
        frame = build_strm_frame(params, "")

        ip = struct.unpack(">I", frame[20:24])[0]
        assert ip == 0

        # 192.168.1.1 = 0xC0A80101
        params = StreamParams(server_ip=0xC0A80101)
        frame = build_strm_frame(params, "")

        ip = struct.unpack(">I", frame[20:24])[0]
        assert ip == 0xC0A80101

    def test_request_string_appended(self) -> None:
        """Request string should be appended after the header."""
        request = "GET /test HTTP/1.0\r\n"
        params = StreamParams()
        frame = build_strm_frame(params, request)

        assert frame[24:] == request.encode("latin-1")

    def test_buffer_threshold(self) -> None:
        """Buffer threshold should be at byte 7."""
        params = StreamParams(buffer_threshold_kb=128)
        frame = build_strm_frame(params, "")

        assert frame[7] == 128

    def test_transition_type(self) -> None:
        """Transition type should be at byte 10."""
        params = StreamParams(transition_type=TransitionType.CROSSFADE)
        frame = build_strm_frame(params, "")

        assert frame[10:11] == b"1"

    def test_flags_byte(self) -> None:
        """Flags should be at byte 11."""
        params = StreamParams(flags=0x80)  # loop infinite
        frame = build_strm_frame(params, "")

        assert frame[11] == 0x80


class TestBuildStreamStart:
    """Tests for build_stream_start convenience function."""

    def test_creates_start_command(self) -> None:
        """Should create a start ('s') command."""
        frame = build_stream_start("aa:bb:cc:dd:ee:ff")

        assert frame[0:1] == b"s"

    def test_includes_player_mac_in_url(self) -> None:
        """Request string should include player MAC."""
        mac = "aa:bb:cc:dd:ee:ff"
        frame = build_stream_start(mac)

        request_string = frame[24:].decode("latin-1")
        assert mac in request_string
        assert "GET /stream.mp3?player=" in request_string

    def test_uses_provided_port(self) -> None:
        """Should use the provided server port."""
        frame = build_stream_start("aa:bb:cc:dd:ee:ff", server_port=8080)

        port = struct.unpack(">H", frame[18:20])[0]
        assert port == 8080

    def test_format_parameter(self) -> None:
        """Should use the provided audio format."""
        frame = build_stream_start("aa:bb:cc:dd:ee:ff", format=AudioFormat.FLAC)

        assert frame[2:3] == b"f"


class TestBuildStreamPause:
    """Tests for build_stream_pause function."""

    def test_creates_pause_command(self) -> None:
        """Should create a pause ('p') command."""
        frame = build_stream_pause()

        assert frame[0:1] == b"p"
        assert len(frame) == STRM_FIXED_HEADER_SIZE

    def test_autostart_off(self) -> None:
        """Autostart should be off for pause."""
        frame = build_stream_pause()

        assert frame[1:2] == b"0"


class TestBuildStreamUnpause:
    """Tests for build_stream_unpause function."""

    def test_creates_unpause_command(self) -> None:
        """Should create an unpause ('u') command."""
        frame = build_stream_unpause()

        assert frame[0:1] == b"u"
        assert len(frame) == STRM_FIXED_HEADER_SIZE


class TestBuildStreamStop:
    """Tests for build_stream_stop function."""

    def test_creates_stop_command(self) -> None:
        """Should create a stop ('q') command."""
        frame = build_stream_stop()

        assert frame[0:1] == b"q"
        assert len(frame) == STRM_FIXED_HEADER_SIZE


class TestBuildStreamFlush:
    """Tests for build_stream_flush function."""

    def test_creates_flush_command(self) -> None:
        """Should create a flush ('f') command."""
        frame = build_stream_flush()

        assert frame[0:1] == b"f"


class TestBuildStreamStatus:
    """Tests for build_stream_status function."""

    def test_creates_status_command(self) -> None:
        """Should create a status ('t') command."""
        frame = build_stream_status()

        assert frame[0:1] == b"t"


class TestBuildAudgFrame:
    """Tests for build_audg_frame function."""

    def test_frame_structure(self) -> None:
        """Frame should have correct size and structure."""
        frame = build_audg_frame()

        # Frame should be 18 bytes (2x4 deprecated + 1 + 1 + 4 + 4)
        assert len(frame) == 18

    def test_deprecated_fields_zero(self) -> None:
        """Old left/right fields should be zero."""
        frame = build_audg_frame()

        old_left = struct.unpack(">I", frame[0:4])[0]
        old_right = struct.unpack(">I", frame[4:8])[0]

        assert old_left == 0
        assert old_right == 0

    def test_digital_volume_flag(self) -> None:
        """Digital volume flag should be at byte 8."""
        frame = build_audg_frame(digital_volume=True)
        assert frame[8] == 1

        frame = build_audg_frame(digital_volume=False)
        assert frame[8] == 0

    def test_preamp_byte(self) -> None:
        """Preamp should be at byte 9."""
        frame = build_audg_frame(preamp=200)
        assert frame[9] == 200

    def test_gain_values(self) -> None:
        """Gain values should be in 16.16 fixed point format."""
        frame = build_audg_frame(left_gain=128, right_gain=256)

        left_fixed = struct.unpack(">I", frame[10:14])[0]
        right_fixed = struct.unpack(">I", frame[14:18])[0]

        # 128 << 8 = 0x8000 (half gain)
        assert left_fixed == 128 << 8
        # 256 << 8 = 0x10000 (unity gain)
        assert right_fixed == 256 << 8


class TestBuildVolumeFrame:
    """Tests for build_volume_frame function."""

    def test_volume_zero(self) -> None:
        """Volume 0 should produce zero gain."""
        frame = build_volume_frame(volume=0)

        left_gain = struct.unpack(">I", frame[10:14])[0]
        right_gain = struct.unpack(">I", frame[14:18])[0]

        assert left_gain == 0
        assert right_gain == 0

    def test_volume_max(self) -> None:
        """Volume 100 should produce maximum gain."""
        frame = build_volume_frame(volume=100)

        left_gain = struct.unpack(">I", frame[10:14])[0]
        right_gain = struct.unpack(">I", frame[14:18])[0]

        # 256 << 8 = 0x10000
        assert left_gain == 256 << 8
        assert right_gain == 256 << 8

    def test_muted_produces_zero(self) -> None:
        """Muted should produce zero gain regardless of volume."""
        frame = build_volume_frame(volume=100, muted=True)

        left_gain = struct.unpack(">I", frame[10:14])[0]
        right_gain = struct.unpack(">I", frame[14:18])[0]

        assert left_gain == 0
        assert right_gain == 0

    def test_volume_50(self) -> None:
        """Volume 50 should produce half gain."""
        frame = build_volume_frame(volume=50)

        left_gain = struct.unpack(">I", frame[10:14])[0]

        # 50% of 256 = 128, then << 8
        expected = int((50 / 100) * 256) << 8
        assert left_gain == expected


class TestEnumValues:
    """Tests for enum value correctness."""

    def test_stream_command_values(self) -> None:
        """StreamCommand values should match protocol spec."""
        assert StreamCommand.START.value == ord("s")
        assert StreamCommand.PAUSE.value == ord("p")
        assert StreamCommand.UNPAUSE.value == ord("u")
        assert StreamCommand.STOP.value == ord("q")
        assert StreamCommand.FLUSH.value == ord("f")
        assert StreamCommand.STATUS.value == ord("t")

    def test_audio_format_values(self) -> None:
        """AudioFormat values should match protocol spec."""
        assert AudioFormat.MP3.value == ord("m")
        assert AudioFormat.PCM.value == ord("p")
        assert AudioFormat.FLAC.value == ord("f")
        assert AudioFormat.OGG.value == ord("o")
        assert AudioFormat.AAC.value == ord("a")
        assert AudioFormat.WMA.value == ord("w")

    def test_autostart_mode_values(self) -> None:
        """AutostartMode values should match protocol spec."""
        assert AutostartMode.OFF.value == ord("0")
        assert AutostartMode.AUTO.value == ord("1")
        assert AutostartMode.DIRECT.value == ord("2")
        assert AutostartMode.DIRECT_AUTO.value == ord("3")

    def test_transition_type_values(self) -> None:
        """TransitionType values should match protocol spec."""
        assert TransitionType.NONE.value == ord("0")
        assert TransitionType.CROSSFADE.value == ord("1")
        assert TransitionType.FADE_IN.value == ord("2")
        assert TransitionType.FADE_OUT.value == ord("3")
        assert TransitionType.FADE_IN_OUT.value == ord("4")
        assert TransitionType.CROSSFADE_IMMEDIATE.value == ord("5")
