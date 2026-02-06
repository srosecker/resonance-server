#!/usr/bin/env python3
"""
Squeezebox Radio Connection Simulator

This script simulates the behavior of a Squeezebox Radio (SqueezePlay) attempting
to connect to the Resonance server via HTTP/Cometd.

It performs the exact same sequence of requests that a real Radio should perform:
1. Bayeux Handshake (POST /cometd)
2. Streaming Connect (POST /cometd)
3. Subscription to serverstatus (POST /cometd)
4. Request for menu (POST /jsonrpc.js)

Usage:
    python debug_radio_simulation.py [server_ip] [server_port]

Example:
    python debug_radio_simulation.py 192.168.1.30 9000
"""

import json
import logging
import sys
import threading
import time
import uuid
from typing import Any

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("RadioSim")

# Default configuration
SERVER_IP = "127.0.0.1"
SERVER_PORT = 9000
MAC_ADDRESS = "00:04:20:26:84:ae"  # Matches the Boom/Radio in your captures
FIRMWARE_REV = "7.7.3 r16676"      # Standard Radio firmware
DEVICE_UUID = uuid.uuid4().hex

def get_url(path: str) -> str:
    return f"http://{SERVER_IP}:{SERVER_PORT}{path}"

def print_response(name: str, resp: requests.Response) -> None:
    try:
        data = resp.json()
        logger.info(f"{name} Response ({resp.status_code}):")
        logger.info(json.dumps(data, indent=2))
        return data
    except Exception:
        logger.info(f"{name} Response ({resp.status_code}): {resp.text[:200]}")
        return None

def simulate_streaming_connection(client_id: str):
    """
    Keeps a streaming connection open to receive events.
    """
    url = get_url("/cometd")

    # 2. Connect (Streaming) + Subscribe
    # SqueezePlay sends connect and subscribe in one batch usually,
    # but sometimes sequentially. Here we match the "ws18" flow if possible.

    payload = [
        {
            "channel": "/meta/connect",
            "clientId": client_id,
            "connectionType": "streaming",
            "id": "2"
        },
        {
            "channel": "/meta/subscribe",
            "clientId": client_id,
            "subscription": f"/{client_id}/**",
            "id": "3"
        }
    ]

    logger.info(f"Opening Streaming Connection to {url}...")

    try:
        with requests.post(url, json=payload, stream=True, timeout=120) as resp:
            logger.info(f"Streaming Connection Established ({resp.status_code})")

            # Read chunked response
            for line in resp.iter_lines():
                if line:
                    logger.info(f"[STREAM] Received: {line.decode('utf-8')}")

    except Exception as e:
        logger.error(f"Streaming Connection Failed: {e}")

def main():
    global SERVER_IP, SERVER_PORT

    if len(sys.argv) > 1:
        SERVER_IP = sys.argv[1]
    if len(sys.argv) > 2:
        SERVER_PORT = int(sys.argv[2])

    logger.info(f"Simulating Squeezebox Radio connecting to {SERVER_IP}:{SERVER_PORT}")

    # 1. Handshake
    handshake_payload = [{
        "channel": "/meta/handshake",
        "version": "1.0",
        "supportedConnectionTypes": ["streaming"],
        "ext": {
            "rev": FIRMWARE_REV,
            "uuid": DEVICE_UUID,
            "mac": MAC_ADDRESS
        },
        "id": "1"
    }]

    logger.info("Sending Handshake...")
    try:
        resp = requests.post(get_url("/cometd"), json=handshake_payload)
        data = print_response("Handshake", resp)

        if not data or not isinstance(data, list) or not data[0].get("successful"):
            logger.error("Handshake failed!")
            return

        client_id = data[0]["clientId"]
        logger.info(f"Handshake successful! Client ID: {client_id}")

    except Exception as e:
        logger.error(f"Could not connect to server: {e}")
        return

    # Start streaming connection in background thread
    stream_thread = threading.Thread(target=simulate_streaming_connection, args=(client_id,))
    stream_thread.daemon = True
    stream_thread.start()

    # Give it a moment to establish
    time.sleep(1)

    # 3. Subscribe to serverstatus (Standard SqueezePlay behavior)
    # This usually happens on a second HTTP connection (rhttp)

    sub_payload = [{
        "channel": "/slim/subscribe",
        "id": "4",
        "clientId": client_id,  # Some clients add this, some don't. We should support both.
        "data": {
            "request": ["", ["serverstatus", 0, 50, "subscribe:60"]],
            "response": f"/{client_id}/slim/serverstatus"
        }
    }]

    logger.info("Sending /slim/subscribe (serverstatus)...")
    try:
        resp = requests.post(get_url("/cometd"), json=sub_payload)
        print_response("Subscription", resp)
    except Exception as e:
        logger.error(f"Subscription failed: {e}")

    # 4. Request Menu (simulate user navigating)
    time.sleep(1)

    menu_payload = [{
        "channel": "/slim/request",
        "id": "5",
        "clientId": client_id,
        "data": {
            "request": [MAC_ADDRESS, ["menu", 0, 100]],
            "response": f"/{client_id}/slim/request"
        }
    }]

    logger.info("Sending /slim/request (menu)...")
    try:
        resp = requests.post(get_url("/cometd"), json=menu_payload)
        print_response("Menu Request", resp)
    except Exception as e:
        logger.error(f"Menu request failed: {e}")

    logger.info("Simulation complete. Keeping stream open for 10s...")
    time.sleep(10)

if __name__ == "__main__":
    main()
