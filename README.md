# 🎵 Resonance

A modern Python implementation of the Logitech Media Server (Squeezebox Server).

## Overview

Resonance is a complete rewrite of the venerable Logitech Media Server (formerly SlimServer) in Python. It aims to provide full compatibility with Squeezebox hardware and software players (like Squeezelite) while offering a cleaner, more maintainable codebase.

## Goals

- **Full Compatibility**: Work with all Squeezebox hardware and Squeezelite
- **Modern Python**: asyncio-based, type-hinted, well-tested
- **Clean Architecture**: Small focused modules, no 4000+ LOC files
- **Better than the Original**: Learn from 20+ years of LMS development

## Status

🚧 **Pre-Alpha** - Active development, not yet functional.

## Requirements

- Python 3.11+
- For transcoding: ffmpeg, flac, sox (same as LMS)

## Installation

```bash
# Clone the repository
git clone https://github.com/resonance-server/resonance.git
cd resonance

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"
```

## Usage

```bash
# Run the server
python -m resonance

# Or after installation
resonance
```

## Development

```bash
# Run tests
pytest

# Type checking
mypy resonance

# Linting
ruff check resonance
```

## Project Structure

```
resonance/
├── resonance/           # Main package
│   ├── protocol/        # Slimproto, CLI protocols
│   ├── player/          # Player management
│   ├── streaming/       # Audio streaming
│   ├── library/         # Music library
│   └── web/             # Web interface
├── tests/               # Test suite
└── docs/                # Documentation
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Changelog](docs/CHANGELOG.md)
- [TODO / Roadmap](docs/TODO.md)

## License

GPL-2.0 (same as the original Logitech Media Server)

## Acknowledgments

- The original [Logitech Media Server](https://github.com/LMS-Community/slimserver) team
- The [LMS Community](https://forums.slimdevices.com/) for keeping Squeezebox alive
- [Squeezelite](https://github.com/ralph-irving/squeezelite) for the excellent software player