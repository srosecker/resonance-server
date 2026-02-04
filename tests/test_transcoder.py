"""
Tests for the streaming transcoder module.

Tests cover:
- Parsing of legacy.conf rules
- Rule matching logic
- Command building
- Binary resolution

Also includes lightweight tests for streaming decision policy to ensure
format-handling behavior stays consistent.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from resonance.streaming.transcoder import (
    TranscodeConfig,
    TranscodeRule,
    build_command,
    parse_legacy_conf,
    resolve_binary,
)


class TestTranscodeRule:
    """Tests for TranscodeRule class."""

    def test_is_passthrough_with_dash(self) -> None:
        """Passthrough rule has '-' as command."""
        rule = TranscodeRule(
            source_format="mp3",
            dest_format="mp3",
            device_type="*",
            device_id="*",
            command="-",
        )
        assert rule.is_passthrough() is True

    def test_is_passthrough_with_command(self) -> None:
        """Non-passthrough rule has actual command."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $FILE$",
        )
        assert rule.is_passthrough() is False

    def test_matches_source_format(self) -> None:
        """Rule matches source format."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $FILE$",
        )
        assert rule.matches("m4b") is True
        assert rule.matches("M4B") is True  # Case insensitive
        assert rule.matches("mp3") is False

    def test_matches_device_type_wildcard(self) -> None:
        """Wildcard device type matches anything."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $FILE$",
        )
        assert rule.matches("m4b", device_type="boom") is True
        assert rule.matches("m4b", device_type="squeezebox") is True

    def test_matches_specific_device_type(self) -> None:
        """Specific device type only matches that device."""
        rule = TranscodeRule(
            source_format="wma",
            dest_format="mp3",
            device_type="slimp3",
            device_id="*",
            command="[wmadec] -w $FILE$",
        )
        assert rule.matches("wma", device_type="slimp3") is True
        assert rule.matches("wma", device_type="boom") is False

    def test_matches_device_id_wildcard(self) -> None:
        """Wildcard device ID matches any MAC."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $FILE$",
        )
        assert rule.matches("m4b", device_id="00:11:22:33:44:55") is True

    def test_matches_specific_device_id(self) -> None:
        """Specific device ID only matches that MAC."""
        rule = TranscodeRule(
            source_format="mp3",
            dest_format="mp3",
            device_type="*",
            device_id="00:11:22:33:44:55",
            command="[lame] --abr 128 $FILE$",
        )
        assert rule.matches("mp3", device_id="00:11:22:33:44:55") is True
        assert rule.matches("mp3", device_id="aa:bb:cc:dd:ee:ff") is False


class TestTranscodeConfig:
    """Tests for TranscodeConfig class."""

    def test_find_rule_matches_first(self) -> None:
        """find_rule returns the first matching rule."""
        rules = [
            TranscodeRule("m4b", "flc", "boom", "*", "[faad] specific"),
            TranscodeRule("m4b", "flc", "*", "*", "[faad] generic"),
        ]
        config = TranscodeConfig(rules=rules)

        # Specific device type should match first rule
        rule = config.find_rule("m4b", device_type="boom")
        assert rule is not None
        assert rule.command == "[faad] specific"

        # Other device should match second rule
        rule = config.find_rule("m4b", device_type="squeezebox")
        assert rule is not None
        assert rule.command == "[faad] generic"

    def test_find_rule_with_dest_format(self) -> None:
        """find_rule can filter by destination format."""
        rules = [
            TranscodeRule("m4b", "flc", "*", "*", "[faad] to flac"),
            TranscodeRule("m4b", "pcm", "*", "*", "[faad] to pcm"),
        ]
        config = TranscodeConfig(rules=rules)

        rule = config.find_rule("m4b", dest_format="pcm")
        assert rule is not None
        assert rule.dest_format == "pcm"

    def test_find_rule_no_match(self) -> None:
        """find_rule returns None if no rule matches."""
        rules = [
            TranscodeRule("mp3", "mp3", "*", "*", "-"),
        ]
        config = TranscodeConfig(rules=rules)

        rule = config.find_rule("m4b")
        assert rule is None

    def test_needs_transcoding_passthrough(self) -> None:
        """Passthrough rules don't need transcoding."""
        rules = [
            TranscodeRule("mp3", "mp3", "*", "*", "-"),
        ]
        config = TranscodeConfig(rules=rules)

        assert config.needs_transcoding("mp3") is False

    def test_needs_transcoding_with_rule(self) -> None:
        """Non-passthrough rules need transcoding."""
        rules = [
            TranscodeRule("m4b", "flc", "*", "*", "[faad] -q $FILE$"),
        ]
        config = TranscodeConfig(rules=rules)

        assert config.needs_transcoding("m4b") is True

    def test_needs_transcoding_no_rule(self) -> None:
        """Unknown formats need transcoding by default (safe fallback)."""
        config = TranscodeConfig(rules=[])

        assert config.needs_transcoding("unknown_format") is True


class TestParseLegacyConf:
    """Tests for parsing legacy.conf files."""

    def test_parse_simple_rule(self) -> None:
        """Parse a simple transcoding rule."""
        config_content = textwrap.dedent("""
            # Comment line
            m4b flc * *
            \t[faad] -q -w -f 1 $FILE$
        """)

        with NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            f.flush()
            config = parse_legacy_conf(Path(f.name))

        assert len(config.rules) == 1
        rule = config.rules[0]
        assert rule.source_format == "m4b"
        assert rule.dest_format == "flc"
        assert rule.device_type == "*"
        assert rule.device_id == "*"
        assert "[faad]" in rule.command

    def test_parse_passthrough_rule(self) -> None:
        """Parse a passthrough rule."""
        config_content = textwrap.dedent("""
            mp3 mp3 * *
            \t-
        """)

        with NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            f.flush()
            config = parse_legacy_conf(Path(f.name))

        assert len(config.rules) == 1
        assert config.rules[0].is_passthrough() is True

    def test_parse_multiple_rules(self) -> None:
        """Parse multiple rules."""
        config_content = textwrap.dedent("""
            m4b flc * *
            \t[faad] -q -w -f 1 $FILE$

            mp3 mp3 * *
            \t-

            wma mp3 slimp3 *
            \t[wmadec] -w $FILE$
        """)

        with NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            f.flush()
            config = parse_legacy_conf(Path(f.name))

        assert len(config.rules) == 3

    def test_parse_with_capabilities(self) -> None:
        """Parse rule with capability flags."""
        config_content = textwrap.dedent("""
            m4b flc * *
            \t# FT
            \t[faad] -q -w -f 1 $FILE$
        """)

        with NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            f.flush()
            config = parse_legacy_conf(Path(f.name))

        assert len(config.rules) == 1
        assert config.rules[0].capabilities == "FT"

    def test_parse_pipeline_command(self) -> None:
        """Parse a piped command."""
        config_content = textwrap.dedent("""
            m4b flc * *
            \t[faad] -q -w -f 1 $FILE$ | [flac] -cs -
        """)

        with NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(config_content)
            f.flush()
            config = parse_legacy_conf(Path(f.name))

        assert len(config.rules) == 1
        assert "|" in config.rules[0].command


class TestBuildCommand:
    """Tests for building command lines."""

    def test_build_simple_command(self) -> None:
        """Build a simple command with file substitution."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="pcm",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 2 $FILE$",
        )

        file_path = Path("/music/audiobook.m4b")

        # Mock resolve_binary to return a path
        import resonance.streaming.transcoder as transcoder_module

        original_resolve = transcoder_module.resolve_binary

        def mock_resolve(name: str) -> Path | None:
            return Path(f"/usr/bin/{name}")

        transcoder_module.resolve_binary = mock_resolve

        try:
            commands = build_command(rule, file_path)
            assert len(commands) == 1
            assert "faad" in commands[0][0]  # Path separator varies by OS
            assert "-q" in commands[0]
            assert str(file_path) in commands[0]
        finally:
            transcoder_module.resolve_binary = original_resolve

    def test_build_pipeline_command(self) -> None:
        """Build a piped command."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $FILE$ | [flac] -cs -",
        )

        file_path = Path("/music/audiobook.m4b")

        import resonance.streaming.transcoder as transcoder_module

        original_resolve = transcoder_module.resolve_binary

        def mock_resolve(name: str) -> Path | None:
            return Path(f"/usr/bin/{name}")

        transcoder_module.resolve_binary = mock_resolve

        try:
            commands = build_command(rule, file_path)
            assert len(commands) == 2
            assert "faad" in commands[0][0]
            assert "flac" in commands[1][0]
        finally:
            transcoder_module.resolve_binary = original_resolve

    def test_build_command_binary_not_found(self) -> None:
        """Raise error if binary not found."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[nonexistent_binary] $FILE$",
        )

        file_path = Path("/music/audiobook.m4b")

        with pytest.raises(ValueError, match="Binary not found"):
            build_command(rule, file_path)

    def test_build_command_with_seek_start(self) -> None:
        """Build command with $START$ placeholder for seeking."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $START$ $END$ $FILE$",
        )

        file_path = Path("/music/audiobook.m4b")

        import resonance.streaming.transcoder as transcoder_module

        original_resolve = transcoder_module.resolve_binary

        def mock_resolve(name: str) -> Path | None:
            return Path(f"/usr/bin/{name}")

        transcoder_module.resolve_binary = mock_resolve

        try:
            # With start_seconds=120.5, should insert -j 120.500
            commands = build_command(rule, file_path, start_seconds=120.5)
            assert len(commands) == 1
            cmd = commands[0]
            assert "-j" in cmd
            assert "120.500" in cmd
            assert str(file_path) in cmd
            # $END$ should be removed (empty) when not specified
            assert "-e" not in cmd
        finally:
            transcoder_module.resolve_binary = original_resolve

    def test_build_command_with_seek_start_and_end(self) -> None:
        """Build command with both $START$ and $END$ placeholders."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $START$ $END$ $FILE$",
        )

        file_path = Path("/music/audiobook.m4b")

        import resonance.streaming.transcoder as transcoder_module

        original_resolve = transcoder_module.resolve_binary

        def mock_resolve(name: str) -> Path | None:
            return Path(f"/usr/bin/{name}")

        transcoder_module.resolve_binary = mock_resolve

        try:
            # With both start and end
            commands = build_command(rule, file_path, start_seconds=60.0, end_seconds=180.0)
            assert len(commands) == 1
            cmd = commands[0]
            assert "-j" in cmd
            assert "60.000" in cmd
            assert "-e" in cmd
            assert "180.000" in cmd
        finally:
            transcoder_module.resolve_binary = original_resolve

    def test_build_command_without_seek(self) -> None:
        """Build command without seek parameters removes placeholders cleanly."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $START$ $END$ $FILE$",
        )

        file_path = Path("/music/audiobook.m4b")

        import resonance.streaming.transcoder as transcoder_module

        original_resolve = transcoder_module.resolve_binary

        def mock_resolve(name: str) -> Path | None:
            return Path(f"/usr/bin/{name}")

        transcoder_module.resolve_binary = mock_resolve

        try:
            # Without seek parameters, $START$ and $END$ should be removed
            commands = build_command(rule, file_path)
            assert len(commands) == 1
            cmd = commands[0]
            assert "-j" not in cmd
            assert "-e" not in cmd
            assert "$START$" not in " ".join(cmd)
            assert "$END$" not in " ".join(cmd)
            assert str(file_path) in cmd
        finally:
            transcoder_module.resolve_binary = original_resolve

    def test_build_command_seek_zero_ignored(self) -> None:
        """Seek of 0 seconds should not add -j flag."""
        rule = TranscodeRule(
            source_format="m4b",
            dest_format="flc",
            device_type="*",
            device_id="*",
            command="[faad] -q -w -f 1 $START$ $END$ $FILE$",
        )

        file_path = Path("/music/audiobook.m4b")

        import resonance.streaming.transcoder as transcoder_module

        original_resolve = transcoder_module.resolve_binary

        def mock_resolve(name: str) -> Path | None:
            return Path(f"/usr/bin/{name}")

        transcoder_module.resolve_binary = mock_resolve

        try:
            # start_seconds=0 should not add -j
            commands = build_command(rule, file_path, start_seconds=0.0)
            assert len(commands) == 1
            cmd = commands[0]
            assert "-j" not in cmd
        finally:
            transcoder_module.resolve_binary = original_resolve


class TestResolveBinary:
    """Tests for binary resolution."""

    def test_resolve_binary_returns_none_for_nonexistent(self) -> None:
        """Returns None for non-existent binaries."""
        result = resolve_binary("this_binary_definitely_does_not_exist_12345")
        assert result is None

    def test_resolve_binary_finds_system_binary(self) -> None:
        """Finds binaries in system PATH."""
        # python should always be available
        result = resolve_binary("python")
        # May or may not be found depending on environment
        # Just verify it returns Path or None
        assert result is None or isinstance(result, Path)


class TestStreamingDecisionLogic:
    """Tests for the shared streaming decision logic (policy module)."""

    def test_mp4_formats_always_need_transcoding(self) -> None:
        """MP4 container formats should always require transcoding."""
        from resonance.streaming.policy import needs_transcoding

        # These formats have HTTP streaming/container issues - always transcode
        for fmt in ["m4a", "m4b", "mp4", "m4p", "m4r", "alac", "aac"]:
            assert needs_transcoding(fmt, None) is True, f"{fmt} should need transcoding"
            assert needs_transcoding(fmt, "squeezeslave") is True, (
                f"{fmt} should need transcoding for modern device"
            )
            assert needs_transcoding(fmt, "boom") is True, (
                f"{fmt} should need transcoding for legacy device"
            )

    def test_strm_hint_matches_transcode_decision(self) -> None:
        """
        If a format is transcoded for streaming, the `strm` hint must signal the
        transcoded output format (currently FLAC) so the player expects the right data.
        """
        from resonance.streaming.policy import (
            DEFAULT_POLICY,
            needs_transcoding,
            strm_expected_format_hint,
        )

        # A few representative device types (string names are accepted)
        device_types = [None, "squeezeslave", "boom"]

        # When transcoding is needed, strm hint must be the transcode target (flac)
        transcode_formats = ["m4a", "m4b", "mp4", "alac", "aac"]
        for device in device_types:
            for fmt in transcode_formats:
                assert needs_transcoding(fmt, device) is True
                assert (
                    strm_expected_format_hint(fmt, device) == DEFAULT_POLICY.TRANSCODE_TARGET_FORMAT
                )

        # When no transcoding is needed, strm hint must remain the normalized input format
        direct_formats = ["mp3", "flac", "ogg", "wav", "aiff", "aif"]
        for device in device_types:
            for fmt in direct_formats:
                assert needs_transcoding(fmt, device) is False
                assert strm_expected_format_hint(fmt, device) == fmt

    def test_native_formats_dont_need_transcoding(self) -> None:
        """Native streaming formats should not require transcoding."""
        from resonance.streaming.policy import needs_transcoding

        # These formats stream reliably over HTTP
        for fmt in ["mp3", "flac", "flc", "ogg", "wav", "aiff", "aif"]:
            assert needs_transcoding(fmt, None) is False, f"{fmt} should NOT need transcoding"
            assert needs_transcoding(fmt, "squeezeslave") is False, (
                f"{fmt} should NOT need transcoding for modern"
            )
            assert needs_transcoding(fmt, "boom") is False, (
                f"{fmt} should NOT need transcoding for legacy"
            )

    def test_case_insensitive_format_check(self) -> None:
        """Format checking should be case insensitive."""
        from resonance.streaming.policy import needs_transcoding

        assert needs_transcoding("M4B", None) is True
        assert needs_transcoding("FLAC", None) is False
        assert needs_transcoding("Mp3", None) is False
