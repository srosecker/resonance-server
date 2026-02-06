"""
Web Server Module for Resonance.

This module provides the WebServer class that creates and manages the
FastAPI application, registers all routes, and handles HTTP/JSON-RPC requests.

The WebServer integrates:
- JSON-RPC endpoint for LMS-compatible clients
- REST API for web UI
- Streaming endpoint for audio playback
- Cometd endpoint for real-time updates
- Artwork endpoint for album covers
"""

from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from resonance.web.cometd import CometdManager
from resonance.web.jsonrpc import JsonRpcHandler
from resonance.web.routes.api import register_api_routes
from resonance.web.routes.artwork import register_artwork_routes
from resonance.web.routes.cometd import register_cometd_routes
from resonance.web.routes.streaming import register_streaming_routes

if TYPE_CHECKING:
    from resonance.core.artwork import ArtworkManager
    from resonance.core.library import MusicLibrary
    from resonance.core.playlist import PlaylistManager
    from resonance.player.registry import PlayerRegistry
    from resonance.protocol.slimproto import SlimprotoServer
    from resonance.streaming.server import StreamingServer

logger = logging.getLogger(__name__)


@dataclass
class JsonRpcRequest:
    """JSON-RPC request model."""

    id: int | str | None = None
    method: str = ""
    params: list[Any] | None = None

    def __post_init__(self) -> None:
        if self.params is None:
            self.params = []


@dataclass
class JsonRpcResponse:
    """JSON-RPC response model."""

    id: int | str | None = None
    method: str = ""
    params: list[Any] | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.params is None:
            self.params = []


class WebServer:
    """
    FastAPI-based web server for Resonance.

    Provides HTTP, JSON-RPC, and streaming endpoints for:
    - LMS-compatible apps (iPeng, Squeezer, Material Skin)
    - Web UI
    - Squeezebox players (audio streaming)
    """

    def __init__(
        self,
        player_registry: PlayerRegistry,
        music_library: MusicLibrary,
        playlist_manager: PlaylistManager | None = None,
        streaming_server: StreamingServer | None = None,
        artwork_manager: ArtworkManager | None = None,
        slimproto: SlimprotoServer | None = None,
        server_uuid: str = "resonance",
    ) -> None:
        """
        Initialize the WebServer.

        Args:
            player_registry: Registry of connected players
            music_library: Music library for browsing/search
            playlist_manager: Optional playlist manager
            streaming_server: Optional streaming server for audio
            artwork_manager: Optional artwork extraction/caching
            slimproto: Optional Slimproto server for player control
            server_uuid: Server UUID for identification (full UUID v4, 36 chars with dashes)
        """
        self.player_registry = player_registry
        self.music_library = music_library
        self.playlist_manager = playlist_manager
        self.streaming_server = streaming_server
        self.artwork_manager = artwork_manager
        self.slimproto = slimproto

        # Create FastAPI app
        self.app = FastAPI(
            title="Resonance",
            description="Modern Python Music Server (LMS-compatible)",
            version="0.1.0",
        )

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # TODO: Make configurable
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Create Cometd manager
        self.cometd_manager = CometdManager()

        # Create JSON-RPC handler
        self.jsonrpc_handler = JsonRpcHandler(
            music_library=music_library,
            player_registry=player_registry,
            playlist_manager=playlist_manager,
            streaming_server=streaming_server,
            slimproto=slimproto,
            artwork_manager=artwork_manager,
            server_uuid=server_uuid,
        )

        # Server state
        self._server: uvicorn.Server | None = None
        self._host = "0.0.0.0"
        self._port = 9000

        # Register routes
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all routes with the FastAPI app."""

        # Health check
        @self.app.get("/health")
        async def health_check() -> dict[str, str]:
            """Health check endpoint."""
            return {"status": "ok", "server": "resonance"}

        # JSON-RPC endpoints
        @self.app.post("/jsonrpc.js", tags=["jsonrpc"])
        async def jsonrpc_endpoint(request: dict[str, Any]) -> dict[str, Any]:
            """Main JSON-RPC endpoint.

            This is the primary API endpoint used by LMS-compatible apps.
            """
            return await self.jsonrpc_handler.handle_request(request)

        @self.app.post("/jsonrpc", tags=["jsonrpc"])
        async def jsonrpc_alt_endpoint(request: dict[str, Any]) -> dict[str, Any]:
            """Alternative JSON-RPC endpoint (without .js extension)."""
            return await self.jsonrpc_handler.handle_request(request)

        # Register API routes
        register_api_routes(
            self.app,
            music_library=self.music_library,
            player_registry=self.player_registry,
            playlist_manager=self.playlist_manager,
        )

        # Register streaming routes
        if self.streaming_server is not None:
            register_streaming_routes(self.app, self.streaming_server)

        # Register artwork routes
        if self.artwork_manager is not None:
            register_artwork_routes(
                self.app,
                artwork_manager=self.artwork_manager,
                music_library=self.music_library,
            )

        # Register Cometd routes
        register_cometd_routes(
            self.app,
            cometd_manager=self.cometd_manager,
            jsonrpc_handler=self.jsonrpc_handler,
        )

    async def start(self, host: str = "0.0.0.0", port: int = 9000) -> None:
        """
        Start the web server.

        Args:
            host: Host address to bind to
            port: Port to listen on
        """
        self._host = host
        self._port = port

        # Update JSON-RPC handler with server info
        # If binding to all interfaces (0.0.0.0), detect the actual LAN IP
        # so Squeezebox devices can construct valid URLs for artwork/streaming
        if host == "0.0.0.0":
            self.jsonrpc_handler.server_host = self._detect_lan_ip()
        else:
            self.jsonrpc_handler.server_host = host
        self.jsonrpc_handler.server_port = port

        # Start Cometd manager
        await self.cometd_manager.start()

        # Configure uvicorn
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        # Start server in background
        import asyncio

        asyncio.create_task(self._server.serve())

        logger.info("Web server started on http://%s:%d", host, port)

    async def stop(self) -> None:
        """Stop the web server."""
        # Stop Cometd manager
        await self.cometd_manager.stop()

        # Stop uvicorn server
        if self._server is not None:
            self._server.should_exit = True
            self._server = None

        logger.info("Web server stopped")

    @property
    def port(self) -> int:
        """Get the server port."""
        return self._port

    @property
    def host(self) -> str:
        """Get the server host."""
        return self._host

    @staticmethod
    def _detect_lan_ip() -> str:
        """
        Detect the primary LAN IP address of this machine.

        Uses the UDP socket trick: connect to a public DNS server
        (no packet is actually sent) to determine which local
        interface would be used for outbound traffic.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
