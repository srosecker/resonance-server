"""
Streaming module for Resonance.

This module provides HTTP streaming endpoints for serving audio
to Squeezebox players.
"""

from resonance.streaming.server import StreamingServer

__all__ = ["StreamingServer"]
