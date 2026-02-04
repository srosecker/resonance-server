"""
Cometd Routes for Resonance.

Provides the /cometd endpoint for Bayeux protocol long-polling,
used by LMS-compatible apps (iPeng, Squeezer, Material Skin) for
real-time player status updates.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request

if TYPE_CHECKING:
    from resonance.web.cometd import CometdManager
    from resonance.web.jsonrpc import JsonRpcHandler

logger = logging.getLogger(__name__)

router = APIRouter()

# References set during route registration
_cometd_manager: CometdManager | None = None
_jsonrpc_handler: JsonRpcHandler | None = None


def register_cometd_routes(
    app,
    cometd_manager: CometdManager,
    jsonrpc_handler: JsonRpcHandler | None = None,
) -> None:
    """
    Register Cometd routes with the FastAPI app.

    Args:
        app: FastAPI application instance
        cometd_manager: CometdManager for session management
        jsonrpc_handler: Optional JsonRpcHandler for /slim/request
    """
    global _cometd_manager, _jsonrpc_handler
    _cometd_manager = cometd_manager
    _jsonrpc_handler = jsonrpc_handler

    # Set the JSON-RPC handler on the manager for /slim/request
    if jsonrpc_handler is not None:
        cometd_manager.set_jsonrpc_handler(jsonrpc_handler)

    app.include_router(router)


@router.post("/cometd/")
@router.post("/cometd")
async def cometd_handler(request: Request) -> list[dict[str, Any]]:
    """
    Handle Cometd/Bayeux protocol requests.

    Accepts an array of Bayeux messages and returns responses.
    Each message has a 'channel' field indicating the operation.

    Meta channels:
    - /meta/handshake: Start a new session, get clientId
    - /meta/connect: Long-poll for events
    - /meta/disconnect: End session
    - /meta/subscribe: Subscribe to channels
    - /meta/unsubscribe: Unsubscribe from channels

    Slim channels:
    - /slim/subscribe: Subscribe to LMS events with a request
    - /slim/unsubscribe: Unsubscribe from LMS events
    - /slim/request: Execute a one-time LMS command
    """
    # Check both global and app.state for cometd_manager
    manager = _cometd_manager
    if manager is None and hasattr(request.app, "state"):
        manager = getattr(request.app.state, "cometd_manager", None)

    if manager is None:
        raise HTTPException(status_code=503, detail="Cometd service not initialized")

    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Invalid JSON in cometd request: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Normalize to list
    messages = body if isinstance(body, list) else [body]

    if not messages:
        raise HTTPException(status_code=400, detail="Empty message list")

    responses: list[dict[str, Any]] = []

    for msg in messages:
        if not isinstance(msg, dict):
            responses.append({"successful": False, "error": "Invalid message format"})
            continue

        channel = msg.get("channel", "")
        msg_id = msg.get("id")
        client_id = msg.get("clientId", "")

        try:
            if channel == "/meta/handshake":
                response = await manager.handshake(msg_id=msg_id)
                responses.append(response)

            elif channel == "/meta/connect":
                result = await manager.connect(
                    client_id=client_id,
                    msg_id=msg_id,
                    timeout_s=60.0,
                )
                # Connect returns a list of responses
                if isinstance(result, list):
                    responses.extend(result)
                else:
                    responses.append(result)

            elif channel == "/meta/disconnect":
                response = await manager.disconnect(
                    client_id=client_id,
                    msg_id=msg_id,
                )
                responses.append(response)

            elif channel == "/meta/subscribe":
                subscription = msg.get("subscription", [])
                result = await manager.subscribe(
                    client_id=client_id,
                    subscription=subscription,
                    msg_id=msg_id,
                )
                # Subscribe returns a list of responses (one per channel)
                responses.extend(result)

            elif channel == "/meta/unsubscribe":
                subscription = msg.get("subscription", [])
                result = await manager.unsubscribe(
                    client_id=client_id,
                    subscription=subscription,
                    msg_id=msg_id,
                )
                # Unsubscribe returns a list of responses (one per channel)
                responses.extend(result)

            elif channel == "/slim/subscribe":
                response = await manager.slim_subscribe(
                    client_id=client_id,
                    request=msg,
                    msg_id=msg_id,
                )
                responses.append(response)

            elif channel == "/slim/unsubscribe":
                response = await manager.slim_unsubscribe(
                    client_id=client_id,
                    request=msg,
                    msg_id=msg_id,
                )
                responses.append(response)

            elif channel == "/slim/request":
                response = await manager.slim_request(
                    client_id=client_id,
                    request=msg,
                    msg_id=msg_id,
                )
                responses.append(response)

            else:
                logger.warning("Unknown cometd channel: %s", channel)
                responses.append(
                    {
                        "channel": channel,
                        "successful": False,
                        "error": f"Unknown channel: {channel}",
                        **({"id": msg_id} if msg_id else {}),
                    }
                )

        except Exception as e:
            logger.exception("Error handling cometd message on %s: %s", channel, e)
            responses.append(
                {
                    "channel": channel,
                    "successful": False,
                    "error": str(e),
                    **({"id": msg_id} if msg_id else {}),
                }
            )

    return responses
