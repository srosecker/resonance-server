"""
Cometd/Bayeux Protocol Implementation for Resonance.

This module implements the Bayeux protocol for real-time push notifications,
enabling LMS-compatible apps (iPeng, Squeezer, Material Skin) to receive
player status updates.

Key classes:
- CometdClient: Represents a connected client session
- CometdManager: Manages client sessions and event delivery
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from resonance.core.events import Event, event_bus

logger = logging.getLogger(__name__)


@dataclass
class CometdClient:
    """
    Represents a Cometd client session.

    Each client has:
    - A unique client_id (8 hex characters)
    - A set of subscribed channels
    - A queue of pending events to deliver
    - Timestamps for session management
    """

    client_id: str
    subscriptions: set[str] = field(default_factory=set)
    pending_events: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Update last_seen timestamp."""
        self.last_seen = time.time()

    def is_expired(self, timeout_s: float = 180.0) -> bool:
        """Check if the client session has expired."""
        return (time.time() - self.last_seen) > timeout_s

    def add_event(self, event: dict[str, Any]) -> None:
        """Add an event to the pending queue."""
        self.pending_events.append(event)

    def get_and_clear_events(self) -> list[dict[str, Any]]:
        """Get all pending events and clear the queue."""
        events = self.pending_events
        self.pending_events = []
        return events


class CometdManager:
    """
    Manages Cometd client sessions and event delivery.

    Implements the Bayeux protocol for:
    - /meta/handshake: Create new client session
    - /meta/connect: Long-polling for events
    - /meta/disconnect: End client session
    - /meta/subscribe: Subscribe to channels
    - /meta/unsubscribe: Unsubscribe from channels
    - /slim/subscribe: LMS-style subscription
    - /slim/unsubscribe: LMS-style unsubscription
    - /slim/request: LMS-style request/response
    """

    def __init__(self) -> None:
        self._clients: dict[str, CometdClient] = {}
        self._lock = asyncio.Lock()
        self._connect_waiters: dict[str, asyncio.Event] = {}
        self._jsonrpc_handler: Any = None  # Set by WebServer for /slim/request

    def set_jsonrpc_handler(self, handler: Any) -> None:
        """Set the JSON-RPC handler for /slim/request."""
        self._jsonrpc_handler = handler

    async def is_valid_client(self, client_id: str) -> bool:
        """Check if a client ID is valid."""
        return client_id in self._clients

    async def get_client_count(self) -> int:
        """Get the number of connected clients."""
        return len(self._clients)

    async def deliver_to_client(
        self,
        client_id: str,
        events: list[dict[str, Any]],
    ) -> bool:
        """
        Deliver events directly to a specific client.

        Args:
            client_id: The client to deliver to
            events: List of event dicts to deliver

        Returns:
            True if delivered, False if client not found
        """
        async with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return False

            for event in events:
                client.add_event(event)

            # Wake up the connect waiter
            waiter = self._connect_waiters.get(client_id)
            if waiter:
                waiter.set()

        return True

    def _generate_client_id(self) -> str:
        """Generate a unique 8-character hex client ID."""
        return secrets.token_hex(4)

    async def handshake(self, msg_id: str | None = None) -> dict[str, Any]:
        """
        Handle /meta/handshake - create a new client session.

        Returns the handshake response with clientId.
        """
        client_id = self._generate_client_id()
        client = CometdClient(client_id=client_id)

        async with self._lock:
            self._clients[client_id] = client
            self._connect_waiters[client_id] = asyncio.Event()

        logger.debug("Handshake: created client %s", client_id)

        response: dict[str, Any] = {
            "id": msg_id if msg_id is not None else "",
            "channel": "/meta/handshake",
            "successful": True,
            "clientId": client_id,
            "version": "1.0",
            "supportedConnectionTypes": ["long-polling", "streaming"],
            "advice": {
                "timeout": 60000,
                "reconnect": "retry",
                "interval": 0,
            },
        }

        return response

    async def connect(
        self,
        client_id: str,
        msg_id: str | None = None,
        timeout_s: float | None = None,
        timeout_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Handle /meta/connect - long-polling for events.

        Waits for events or timeout, then returns pending events.

        Args:
            client_id: The client ID
            msg_id: Optional message ID
            timeout_s: Timeout in seconds (default 60)
            timeout_ms: Timeout in milliseconds (overrides timeout_s if provided)

        Returns:
            List of response messages (connect response + any events)
        """
        # Handle timeout_ms for backwards compat with tests
        if timeout_ms is not None:
            actual_timeout = timeout_ms / 1000.0
        elif timeout_s is not None:
            actual_timeout = timeout_s
        else:
            actual_timeout = 60.0

        async with self._lock:
            client = self._clients.get(client_id)
            waiter = self._connect_waiters.get(client_id)

        if client is None:
            return [
                {
                    "channel": "/meta/connect",
                    "successful": False,
                    "error": "invalid clientId",
                    "advice": {"reconnect": "handshake"},
                    **({"id": msg_id} if msg_id else {}),
                }
            ]

        client.touch()

        # Check for pending events
        events = client.get_and_clear_events()
        if events:
            response: dict[str, Any] = {
                "channel": "/meta/connect",
                "successful": True,
                "clientId": client_id,
            }
            if msg_id is not None:
                response["id"] = msg_id
            return [response] + events

        # Wait for events or timeout
        if waiter:
            try:
                await asyncio.wait_for(waiter.wait(), timeout=actual_timeout)
                waiter.clear()
            except asyncio.TimeoutError:
                pass

        # Get any events that arrived
        events = client.get_and_clear_events()

        response = {
            "channel": "/meta/connect",
            "successful": True,
            "clientId": client_id,
        }
        if msg_id is not None:
            response["id"] = msg_id

        return [response] + events

    async def disconnect(
        self,
        client_id: str,
        msg_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Handle /meta/disconnect - end client session.
        """
        async with self._lock:
            client = self._clients.pop(client_id, None)
            self._connect_waiters.pop(client_id, None)

        if client is None:
            return {
                "channel": "/meta/disconnect",
                "successful": False,
                "error": "Unknown client ID",
                **({"id": msg_id} if msg_id else {}),
            }

        logger.debug("Disconnect: removed client %s", client_id)

        response: dict[str, Any] = {
            "channel": "/meta/disconnect",
            "successful": True,
            "clientId": client_id,
        }
        if msg_id is not None:
            response["id"] = msg_id

        return response

    async def subscribe(
        self,
        client_id: str,
        subscription: str | list[str] | None = None,
        subscriptions: list[str] | None = None,
        msg_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Handle /meta/subscribe - subscribe to channels.

        Returns a list of responses, one per subscription channel.

        Args:
            client_id: The client ID
            subscription: Single subscription or list (Bayeux style)
            subscriptions: List of subscriptions (alternative parameter name)
            msg_id: Optional message ID
        """
        async with self._lock:
            client = self._clients.get(client_id)

        if client is None:
            return [
                {
                    "channel": "/meta/subscribe",
                    "successful": False,
                    "error": "invalid clientId",
                    **({"id": msg_id} if msg_id else {}),
                }
            ]

        client.touch()

        # Normalize to list - support both parameter names
        if subscriptions is not None:
            channels = subscriptions
        elif subscription is not None:
            channels = [subscription] if isinstance(subscription, str) else subscription
        else:
            channels = []

        responses: list[dict[str, Any]] = []
        for channel in channels:
            client.subscriptions.add(channel)
            logger.debug("Client %s subscribed to %s", client_id, channel)
            response: dict[str, Any] = {
                "channel": "/meta/subscribe",
                "successful": True,
                "clientId": client_id,
                "subscription": channel,
            }
            if msg_id is not None:
                response["id"] = msg_id
            responses.append(response)

        return responses

    async def unsubscribe(
        self,
        client_id: str,
        subscription: str | list[str] | None = None,
        subscriptions: list[str] | None = None,
        msg_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Handle /meta/unsubscribe - unsubscribe from channels.

        Returns a list of responses, one per unsubscribed channel.
        """
        async with self._lock:
            client = self._clients.get(client_id)

        if client is None:
            return [
                {
                    "channel": "/meta/unsubscribe",
                    "successful": False,
                    "error": "invalid clientId",
                    **({"id": msg_id} if msg_id else {}),
                }
            ]

        client.touch()

        # Normalize to list - support both parameter names
        if subscriptions is not None:
            channels = subscriptions
        elif subscription is not None:
            channels = [subscription] if isinstance(subscription, str) else subscription
        else:
            channels = []

        responses: list[dict[str, Any]] = []
        for channel in channels:
            client.subscriptions.discard(channel)
            logger.debug("Client %s unsubscribed from %s", client_id, channel)
            response: dict[str, Any] = {
                "channel": "/meta/unsubscribe",
                "successful": True,
                "clientId": client_id,
                "subscription": channel,
            }
            if msg_id is not None:
                response["id"] = msg_id
            responses.append(response)

        return responses

    async def slim_subscribe(
        self,
        client_id: str,
        request: dict[str, Any] | None = None,
        response_channel: str | None = None,
        msg_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Handle /slim/subscribe - LMS-style subscription.

        The request contains response channels and commands to subscribe to.
        Like LMS, we:
        1. Execute the request immediately
        2. Send the initial result to the client
        3. Subscribe for future updates

        Args:
            client_id: The client ID
            request: Full request dict (Bayeux style)
            response_channel: Direct response channel (test-friendly)
            msg_id: Optional message ID

        NOTE (Boom/Jive quirk):
        Some devices embed the clientId only in data.response and may send requests/subscribes
        that reference a clientId we haven't seen via /meta/handshake in this process lifetime.
        To behave like LMS (tolerant), we auto-create the session.
        """
        async with self._lock:
            client = self._clients.get(client_id)

            if client is None:
                # Auto-create missing client session (tolerate embedded clientId usage)
                client = CometdClient(client_id=client_id)
                self._clients[client_id] = client
                self._connect_waiters[client_id] = asyncio.Event()
                logger.warning(
                    "Auto-created missing Cometd client %s from embedded clientId in /slim/subscribe",
                    client_id,
                )

        client.touch()

        resp_ch = response_channel
        req_data = None

        # Extract response channel and request data from request
        # Support both dict format (Bayeux style) and list format (test-friendly)
        if request:
            if isinstance(request, dict):
                data = request.get("data", {})
                if isinstance(data, dict):
                    resp_ch = resp_ch or data.get("response")
                    req_data = data.get("request")
            elif isinstance(request, list):
                # Test-friendly format: [player_id, command_array]
                req_data = request

        # Subscribe to the response channel
        if resp_ch:
            client.subscriptions.add(resp_ch)
            logger.debug("Client %s slim-subscribed to %s", client_id, resp_ch)

        # Execute the request and deliver initial result (like LMS does)
        if req_data is not None and self._jsonrpc_handler is not None:
            try:
                # req_data is [player_id, command_array] e.g. ["", ["serverstatus", 0, 50, "subscribe:60"]]
                if isinstance(req_data, list) and len(req_data) >= 2:
                    player_id = req_data[0] if req_data[0] else ""
                    command = req_data[1]

                    logger.debug(
                        "Client %s slim_subscribe executing: player=%s cmd=%s",
                        client_id, player_id, command
                    )

                    # Execute the JSON-RPC command
                    result = await self._jsonrpc_handler(player_id, command)

                    # Deliver the initial result to the client on the response channel
                    if resp_ch and result:
                        initial_event = {
                            "channel": resp_ch,
                            "id": msg_id,
                            "data": result,
                        }
                        client.add_event(initial_event)
                        logger.debug(
                            "Client %s slim_subscribe delivered initial result on %s",
                            client_id, resp_ch
                        )

                        # Wake up any waiters so they can deliver the event
                        async with self._lock:
                            waiter = self._connect_waiters.get(client_id)
                            if waiter:
                                waiter.set()

            except Exception as e:
                logger.exception("Error executing slim_subscribe request: %s", e)

        response_dict: dict[str, Any] = {
            "channel": "/slim/subscribe",
            "successful": True,
            "clientId": client_id,
        }
        if msg_id is not None:
            response_dict["id"] = msg_id

        return response_dict

    async def slim_unsubscribe(
        self,
        client_id: str,
        request: dict[str, Any] | None = None,
        unsubscribe_channel: str | None = None,
        msg_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Handle /slim/unsubscribe - LMS-style unsubscription.

        Args:
            client_id: The client ID
            request: Full request dict (Bayeux style)
            unsubscribe_channel: Direct channel to unsubscribe (test-friendly)
            msg_id: Optional message ID

        NOTE (Boom/Jive quirk):
        Unsubscribe may arrive referencing a clientId embedded in data.response without a
        prior /meta/handshake in this process lifetime. Be tolerant and auto-create.
        """
        async with self._lock:
            client = self._clients.get(client_id)

            if client is None:
                # Auto-create missing client session (tolerate embedded clientId usage)
                client = CometdClient(client_id=client_id)
                self._clients[client_id] = client
                self._connect_waiters[client_id] = asyncio.Event()
                logger.warning(
                    "Auto-created missing Cometd client %s from embedded clientId in /slim/unsubscribe",
                    client_id,
                )

        client.touch()

        # Extract channels to unsubscribe
        if unsubscribe_channel:
            client.subscriptions.discard(unsubscribe_channel)
        elif request:
            unsubscribe = request.get("unsubscribe")
            if unsubscribe:
                channels = [unsubscribe] if isinstance(unsubscribe, str) else unsubscribe
                for channel in channels:
                    client.subscriptions.discard(channel)

        response_dict: dict[str, Any] = {
            "channel": "/slim/unsubscribe",
            "successful": True,
            "clientId": client_id,
        }
        if msg_id is not None:
            response_dict["id"] = msg_id

        return response_dict

    async def slim_request(
        self,
        client_id: str,
        request: dict[str, Any],
        msg_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Handle /slim/request - execute a JSON-RPC command.

        Like LMS, this:
        1. Executes the request
        2. Sends the result on the response channel (for streaming clients)
        3. Returns a success/failure response

        This delegates to the JSON-RPC handler if set.

        NOTE (Boom/Jive quirk):
        Some devices embed the clientId only in data.response (e.g. "/7a6364c4/slim/request")
        and may send /slim/request before we have seen a /meta/handshake for that id
        (e.g. after a server restart). LMS is tolerant here, so we auto-create the session.
        """
        async with self._lock:
            client = self._clients.get(client_id)

            if client is None:
                # Auto-create missing client session (tolerate embedded clientId usage)
                client = CometdClient(client_id=client_id)
                self._clients[client_id] = client
                self._connect_waiters[client_id] = asyncio.Event()
                logger.warning(
                    "Auto-created missing Cometd client %s from embedded clientId in /slim/request",
                    client_id,
                )

        client.touch()

        # Extract the request data and response channel
        # Format: {"data": {"request": [player_id, command], "response": "/clientId/slim/request"}}
        data = request.get("data", {})
        req_data = None
        resp_channel = None

        if isinstance(data, dict):
            req_data = data.get("request")
            resp_channel = data.get("response")
        elif isinstance(data, list):
            req_data = data

        result: dict[str, Any] = {}
        has_error = False

        if self._jsonrpc_handler is not None and req_data is not None:
            try:
                # req_data is [player_id, command_array]
                if isinstance(req_data, list) and len(req_data) >= 2:
                    player_id = req_data[0] if req_data[0] else ""
                    command = req_data[1]
                    logger.debug(
                        "slim_request executing: player=%s cmd=%s",
                        player_id, command
                    )
                    result = await self._jsonrpc_handler(player_id, command)

                    # Like LMS: deliver the result on the response channel for streaming clients
                    if resp_channel and result:
                        event = {
                            "channel": resp_channel,
                            "id": msg_id,
                            "data": result,
                        }
                        client.add_event(event)
                        logger.debug(
                            "slim_request delivered result on %s",
                            resp_channel
                        )

                        # Wake up any waiters so they can deliver the event
                        async with self._lock:
                            waiter = self._connect_waiters.get(client_id)
                            if waiter:
                                waiter.set()

            except Exception as e:
                logger.exception("Error in slim_request: %s", e)
                result = {"error": str(e)}
                has_error = True

        # Return the acknowledgement (like LMS does)
        # The actual data is delivered via the response channel
        response: dict[str, Any] = {
            "channel": "/slim/request",
            "successful": not has_error,
            "clientId": client_id,
        }
        if has_error:
            response["error"] = result.get("error", "Unknown error")
        if msg_id is not None:
            response["id"] = msg_id

        return response

    async def deliver_event(
        self,
        channel: str,
        data: dict[str, Any],
    ) -> int:
        """
        Deliver an event to all subscribed clients.

        Supports wildcard matching:
        - "*" matches one segment
        - "**" matches multiple segments

        Returns the number of clients that received the event.
        """
        event = {
            "channel": channel,
            "data": data,
        }

        delivered_count = 0

        async with self._lock:
            for client_id, client in self._clients.items():
                if self._matches_any_subscription(channel, client.subscriptions):
                    client.add_event(event)
                    delivered_count += 1

                    # Wake up the connect waiter
                    waiter = self._connect_waiters.get(client_id)
                    if waiter:
                        waiter.set()

        logger.debug(
            "Delivered event on %s to %d clients",
            channel,
            delivered_count,
        )

        return delivered_count

    def _matches_any_subscription(
        self,
        channel: str,
        subscriptions: set[str],
    ) -> bool:
        """Check if a channel matches any subscription pattern."""
        for pattern in subscriptions:
            if self._matches_pattern(channel, pattern):
                return True
        return False

    def _matches_pattern(self, channel: str, pattern: str) -> bool:
        """
        Match a channel against a subscription pattern.

        Patterns:
        - Exact match: "/foo/bar" matches "/foo/bar"
        - Single wildcard: "/foo/*" matches "/foo/bar" but not "/foo/bar/baz"
        - Multi wildcard: "/foo/**" matches "/foo/bar" and "/foo/bar/baz"
        """
        if pattern == channel:
            return True

        # Handle ** (multi-level wildcard)
        if "**" in pattern:
            # Convert to regex-like matching
            pattern_parts = pattern.split("/")
            channel_parts = channel.split("/")

            pattern_idx = 0
            channel_idx = 0

            while pattern_idx < len(pattern_parts) and channel_idx < len(channel_parts):
                p = pattern_parts[pattern_idx]
                c = channel_parts[channel_idx]

                if p == "**":
                    # ** matches zero or more segments
                    # Check if this is the last pattern part
                    if pattern_idx == len(pattern_parts) - 1:
                        return True
                    # Try to match remaining pattern
                    remaining_pattern = "/".join(pattern_parts[pattern_idx + 1 :])
                    for i in range(channel_idx, len(channel_parts)):
                        remaining_channel = "/".join(channel_parts[i:])
                        if self._matches_pattern(remaining_channel, remaining_pattern):
                            return True
                    return False
                elif p == "*":
                    # * matches exactly one segment
                    pattern_idx += 1
                    channel_idx += 1
                elif p == c:
                    pattern_idx += 1
                    channel_idx += 1
                else:
                    return False

            # Check if we consumed all parts
            if pattern_idx == len(pattern_parts) and channel_idx == len(channel_parts):
                return True

            # Handle trailing **
            if pattern_idx < len(pattern_parts) and pattern_parts[pattern_idx] == "**":
                return True

            return False

        # Handle * (single-level wildcard) - must match exactly one segment
        if "*" in pattern:
            pattern_parts = pattern.split("/")
            channel_parts = channel.split("/")

            # Must have same number of segments for single wildcard
            if len(pattern_parts) != len(channel_parts):
                return False

            for p, c in zip(pattern_parts, channel_parts):
                if p == "*":
                    # * matches any single segment (but not empty)
                    if not c:
                        return False
                elif p != c:
                    return False

            return True

        return False

    async def handle_event(self, event: Event) -> None:
        """
        Handle an event from the event bus and deliver to subscribers.

        Maps internal events to Cometd channels.
        """
        from resonance.core.events import (
            PlayerConnectedEvent,
            PlayerDisconnectedEvent,
            PlayerStatusEvent,
        )

        if isinstance(event, PlayerStatusEvent):
            channel = f"/{event.player_id}/status"
            await self.deliver_event(channel, event.to_dict())

        elif isinstance(event, PlayerConnectedEvent):
            channel = "/players"
            await self.deliver_event(
                channel,
                {"event": "connected", "player_id": event.player_id},
            )

        elif isinstance(event, PlayerDisconnectedEvent):
            channel = "/players"
            await self.deliver_event(
                channel,
                {"event": "disconnected", "player_id": event.player_id},
            )

    async def start(self) -> None:
        """Start the Cometd manager and subscribe to events."""
        await event_bus.subscribe("player.*", self.handle_event)
        logger.info("CometdManager started")

    async def stop(self) -> None:
        """Stop the Cometd manager and clean up."""
        async with self._lock:
            self._clients.clear()
            self._connect_waiters.clear()
        logger.info("CometdManager stopped")

    def get_client(self, client_id: str) -> CometdClient | None:
        """Get a client by ID."""
        return self._clients.get(client_id)

    @property
    def client_count(self) -> int:
        """Get the number of connected clients."""
        return len(self._clients)
