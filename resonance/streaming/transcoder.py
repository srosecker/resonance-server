"""
Transcoder module for legacy Squeezebox devices.

This module parses legacy.conf rules and provides on-the-fly transcoding
for audio formats that legacy hardware cannot decode natively.

The transcoding pipeline streams audio through external binaries (faad, flac, sox, lame)
and yields chunks for HTTP streaming.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

if TYPE_CHECKING:
    from resonance.player.client import DeviceType

logger = logging.getLogger(__name__)

# Path to config and binaries
CONFIG_DIR = Path(__file__).parent.parent / "config"
THIRD_PARTY_BIN = Path(__file__).parent.parent.parent / "third_party" / "bin"

# Buffer size for streaming (64KB chunks)
STREAM_BUFFER_SIZE = 65536


@dataclass
class TranscodeRule:
    """A single transcoding rule from legacy.conf."""

    source_format: str
    dest_format: str
    device_type: str  # Device type pattern (* = any)
    device_id: str  # Device MAC pattern (* = any)
    command: str  # Command line template or "-" for passthrough
    capabilities: str = ""  # F, I, T flags

    def is_passthrough(self) -> bool:
        """Check if this rule is passthrough (no transcoding)."""
        return self.command.strip() == "-"

    def matches(
        self,
        source_format: str,
        device_type: str | None = None,
        device_id: str | None = None,
    ) -> bool:
        """
        Check if this rule matches the given parameters.

        Args:
            source_format: Source file format (e.g., "m4b").
            device_type: Device type name (optional).
            device_id: Device MAC address (optional).

        Returns:
            True if this rule matches.
        """
        # Check source format
        if self.source_format != source_format.lower():
            return False

        # Check device type (if specified)
        if device_type and self.device_type != "*":
            if self.device_type.lower() != device_type.lower():
                return False

        # Check device ID (if specified)
        if device_id and self.device_id != "*":
            if self.device_id.lower() != device_id.lower():
                return False

        return True


@dataclass
class TranscodeConfig:
    """Loaded transcoding configuration."""

    rules: list[TranscodeRule]

    def find_rule(
        self,
        source_format: str,
        dest_format: str | None = None,
        device_type: str | None = None,
        device_id: str | None = None,
    ) -> TranscodeRule | None:
        """
        Find the first matching transcoding rule.

        More specific rules (with device_type/device_id) are checked first
        because they should appear earlier in the config file.

        Args:
            source_format: Source file format (e.g., "m4b").
            dest_format: Desired output format (optional, None = any).
            device_type: Device type name (optional).
            device_id: Device MAC address (optional).

        Returns:
            The first matching TranscodeRule, or None if no match.
        """
        source_format = source_format.lower().lstrip(".")

        for rule in self.rules:
            if not rule.matches(source_format, device_type, device_id):
                continue

            # Check dest format if specified
            if dest_format and rule.dest_format != dest_format.lower():
                continue

            return rule

        return None

    def needs_transcoding(
        self,
        source_format: str,
        device_type: str | None = None,
        device_id: str | None = None,
    ) -> bool:
        """
        Check if a format needs transcoding for the given device.

        Args:
            source_format: Source file format (e.g., "m4b").
            device_type: Device type name (optional).
            device_id: Device MAC address (optional).

        Returns:
            True if transcoding is needed (rule exists and is not passthrough).
        """
        rule = self.find_rule(source_format, device_type=device_type, device_id=device_id)

        if rule is None:
            # No rule found - assume transcoding needed for safety
            return True

        return not rule.is_passthrough()


def parse_legacy_conf(config_path: Path | None = None) -> TranscodeConfig:
    """
    Parse the legacy.conf transcoding configuration file.

    Args:
        config_path: Path to legacy.conf. If None, uses default location.

    Returns:
        Parsed TranscodeConfig.
    """
    if config_path is None:
        config_path = CONFIG_DIR / "legacy.conf"

    logger.debug("Loading transcode config from %s", config_path)

    rules: list[TranscodeRule] = []
    current_header: tuple[str, str, str, str] | None = None
    current_capabilities: str = ""

    with config_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            # Strip whitespace
            line = line.rstrip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                # Check for capability comment (# F, # FT, etc.)
                if line.startswith("#") and len(line) <= 10:
                    caps_match = re.match(r"#\s*([FIRTDBU]+)", line)
                    if caps_match:
                        current_capabilities = caps_match.group(1)
                continue

            # Check if this is a header line (format definition)
            parts = line.split()
            if len(parts) == 4 and not line.startswith("\t") and not line.startswith(" "):
                # This is a header: source dest device_type device_id
                current_header = (parts[0], parts[1], parts[2], parts[3])
                current_capabilities = ""
                continue

            # This should be a command line (indented)
            if current_header and (line.startswith("\t") or line.startswith(" ")):
                command = line.strip()

                # Check for inline capability comment
                if command.startswith("#"):
                    caps_match = re.match(r"#\s*([FIRTDBU]+)", command)
                    if caps_match:
                        current_capabilities = caps_match.group(1)
                    continue

                source, dest, dev_type, dev_id = current_header
                rules.append(
                    TranscodeRule(
                        source_format=source.lower(),
                        dest_format=dest.lower(),
                        device_type=dev_type,
                        device_id=dev_id,
                        command=command,
                        capabilities=current_capabilities,
                    )
                )
                current_header = None
                current_capabilities = ""

    logger.info("Loaded %d transcoding rules from %s", len(rules), config_path.name)
    return TranscodeConfig(rules=rules)


def resolve_binary(name: str) -> Path | None:
    """
    Resolve a binary name to its full path.

    Searches in order:
    1. third_party/bin/ directory
    2. System PATH

    Args:
        name: Binary name (e.g., "faad", "flac").

    Returns:
        Path to the binary, or None if not found.
    """
    # Check third_party/bin first
    for ext in ["", ".exe"]:
        bin_path = THIRD_PARTY_BIN / f"{name}{ext}"
        if bin_path.exists():
            return bin_path

    # Check system PATH
    system_path = shutil.which(name)
    if system_path:
        return Path(system_path)

    return None


def build_command(
    rule: TranscodeRule,
    file_path: Path,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
) -> list[list[str]]:
    """
    Build the command pipeline from a transcoding rule.

    Args:
        rule: The TranscodeRule to use.
        file_path: Path to the source audio file.
        start_seconds: Optional seek start position in seconds (for faad -j).
        end_seconds: Optional seek end position in seconds (for faad -e).

    Returns:
        List of command lists (for piping). Each inner list is a command + args.

    Raises:
        ValueError: If a required binary is not found.
    """
    command = rule.command

    # Split on pipe for pipeline commands
    pipe_parts = [p.strip() for p in command.split("|")]

    result: list[list[str]] = []

    for part in pipe_parts:
        # Use shlex to split arguments correctly (handles quotes)
        # Note: we use posix=False on Windows to better handle backslashes in paths
        # if they were present, but here we are parsing the config command line.
        # legacy.conf uses shell-like syntax.
        args = shlex.split(part)

        if not args:
            continue

        # Check for [binary] syntax in the first argument
        binary_match = re.match(r"\[(\w+)\]", args[0])
        if binary_match:
            binary_name = binary_match.group(1)
            binary_path = resolve_binary(binary_name)
            if binary_path is None:
                raise ValueError(f"Binary not found: {binary_name}")

            # Replace the [binary] placeholder with the full path
            cmd_args = [str(binary_path)] + args[1:]
        else:
            # Plain command - use as is (system path resolution happens in subprocess)
            cmd_args = args

        # Perform placeholder substitution on arguments
        final_args = []
        for arg in cmd_args:
            # Replace $FILE$
            if "$FILE$" in arg:
                arg = arg.replace("$FILE$", str(file_path))

            # Replace $START$
            if "$START$" in arg:
                if start_seconds is not None and start_seconds > 0:
                    # Special handling if $START$ is the whole argument or part of it
                    # In legacy.conf: [faad] ... $START$ ...
                    # This usually expands to "-j 123.456".
                    # If it's a separate token in shlex.split, we might need to split it again
                    # or returning multiple args.
                    replacement = f"-j {start_seconds:.3f}"
                    if arg == "$START$":
                        final_args.extend(replacement.split())
                        continue
                    else:
                        arg = arg.replace("$START$", replacement)
                else:
                    # Remove the placeholder
                    if arg == "$START$":
                        continue
                    arg = arg.replace("$START$", "")

            # Replace $END$
            if "$END$" in arg:
                if end_seconds is not None and end_seconds > 0:
                    replacement = f"-e {end_seconds:.3f}"
                    if arg == "$END$":
                        final_args.extend(replacement.split())
                        continue
                    else:
                        arg = arg.replace("$END$", replacement)
                else:
                    if arg == "$END$":
                        continue
                    arg = arg.replace("$END$", "")

            if arg:
                final_args.append(arg)

        result.append(final_args)

    return result


async def _pipe_data(
    source: asyncio.StreamReader,
    dest: asyncio.StreamWriter,
) -> None:
    """
    Copy data from source StreamReader to dest StreamWriter.

    This is needed on Windows because asyncio subprocess pipes cannot be
    directly connected - we must manually copy the data.
    """
    try:
        while True:
            chunk = await source.read(STREAM_BUFFER_SIZE)
            if not chunk:
                break
            dest.write(chunk)
            await dest.drain()
    except Exception as e:
        logger.debug("Pipe data error (may be expected on close): %s", e)
    finally:
        try:
            dest.close()
            await dest.wait_closed()
        except Exception:
            pass


async def transcode_stream(
    file_path: Path,
    rule: TranscodeRule,
    start_seconds: float | None = None,
    end_seconds: float | None = None,
) -> AsyncGenerator[bytes, None]:
    """
    Stream transcoded audio data using the specified rule.

    This sets up a subprocess pipeline and yields chunks of transcoded data.

    On Windows, asyncio subprocess pipes cannot be directly chained (no fileno()),
    so we manually copy data between processes using background tasks.

    Args:
        file_path: Path to the source audio file.
        rule: TranscodeRule specifying how to transcode.
        start_seconds: Optional seek start position in seconds.
        end_seconds: Optional seek end position in seconds.

    Yields:
        Chunks of transcoded audio data.

    Raises:
        ValueError: If the rule is passthrough or binary not found.
        RuntimeError: If transcoding fails.
    """
    if rule.is_passthrough():
        raise ValueError("Cannot transcode with passthrough rule")

    # Build the command pipeline
    try:
        commands = build_command(rule, file_path, start_seconds, end_seconds)
    except ValueError as e:
        logger.error("Failed to build transcode command: %s", e)
        raise

    if start_seconds:
        logger.info(
            "Starting transcode: %s -> %s using %d command(s), seeking to %.1fs",
            file_path.name,
            rule.dest_format,
            len(commands),
            start_seconds,
        )
    else:
        logger.info(
            "Starting transcode: %s -> %s using %d command(s)",
            file_path.name,
            rule.dest_format,
            len(commands),
        )

    # Set up the pipeline
    processes: list[asyncio.subprocess.Process] = []
    pipe_tasks: list[asyncio.Task[None]] = []

    try:
        # Start all processes
        for i, cmd in enumerate(commands):
            is_first = i == 0
            is_last = i == len(commands) - 1

            logger.debug("Starting subprocess %d: %s", i, " ".join(cmd))

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=None if is_first else asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,  # Capture stderr for logging
            )
            processes.append(proc)

        # Connect processes with pipe tasks (for multi-stage pipelines)
        for i in range(len(processes) - 1):
            source_proc = processes[i]
            dest_proc = processes[i + 1]

            if source_proc.stdout is None or dest_proc.stdin is None:
                raise RuntimeError(f"Missing pipe for process {i}")

            # Create background task to copy data between processes
            task = asyncio.create_task(_pipe_data(source_proc.stdout, dest_proc.stdin))
            pipe_tasks.append(task)

        # Read from the last process's stdout
        final_proc = processes[-1]
        if final_proc.stdout is None:
            raise RuntimeError("No stdout from transcode process")

        bytes_yielded = 0
        while True:
            chunk = await final_proc.stdout.read(STREAM_BUFFER_SIZE)
            if not chunk:
                break
            bytes_yielded += len(chunk)
            yield chunk

        # Wait for processes to finish and check for errors
        for i, proc in enumerate(processes):
            if proc.returncode is None:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

            if proc.returncode is not None and proc.returncode != 0:
                stderr_data = b""
                if proc.stderr:
                    stderr_data = await proc.stderr.read()

                logger.warning(
                    "Transcode process %d exited with code %d: %s",
                    i,
                    proc.returncode,
                    stderr_data.decode(errors="ignore")[:500] if stderr_data else "no stderr",
                )

        logger.info(
            "Transcode complete: %s, yielded %d bytes",
            file_path.name,
            bytes_yielded,
        )

    finally:
        # Cancel pipe tasks
        for task in pipe_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        # Clean up all processes
        for proc in processes:
            if proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    proc.kill()
                except Exception:
                    pass


def get_output_content_type(dest_format: str) -> str:
    """
    Get the MIME content type for the transcoded output format.

    Args:
        dest_format: Output format (flc, pcm, mp3, etc.).

    Returns:
        MIME type string.
    """
    content_types = {
        "flc": "audio/flac",
        "flac": "audio/flac",
        "pcm": "audio/L16",
        "mp3": "audio/mpeg",
        "aac": "audio/aac",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
    }
    return content_types.get(dest_format.lower(), "application/octet-stream")


# Global singleton instance (lazy loaded)
_transcode_config: TranscodeConfig | None = None


def get_transcode_config() -> TranscodeConfig:
    """
    Get the global transcoding configuration (lazy loaded singleton).

    Returns:
        The TranscodeConfig instance.
    """
    global _transcode_config

    if _transcode_config is None:
        _transcode_config = parse_legacy_conf()

    return _transcode_config


def reload_transcode_config() -> TranscodeConfig:
    """
    Force reload of transcoding configuration.

    Returns:
        The newly loaded TranscodeConfig instance.
    """
    global _transcode_config
    _transcode_config = parse_legacy_conf()
    return _transcode_config
