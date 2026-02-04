"""
Resonance - A modern Python implementation of the Logitech Media Server.

Resonance provides full compatibility with Squeezebox hardware and software
players while offering a cleaner, more maintainable codebase built on modern
Python patterns.
"""

__version__ = "0.1.0"
__author__ = "Resonance Contributors"
__license__ = "GPL-2.0"

from resonance.server import ResonanceServer

__all__ = ["ResonanceServer", "__version__"]
