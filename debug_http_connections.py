"""
HTTP Connection Debug Script for Resonance.

This script monitors incoming HTTP connections on port 9000 to help debug
why the Squeezebox Boom's Touch-UI (SqueezePlay) isn't making HTTP/Cometd requests.

Run this INSTEAD of the Resonance server to see raw HTTP traffic.

Usage:
    python debug_http_connections.py [port]

    Default port is 9000.
"""

import asyncio
import socket
import sys
from datetime import datetime


class HTTPConnectionDebugger:
    """Simple TCP server that logs all incoming connections and data."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9000):
        self.host = host
        self.port = port
        self.connection_count = 0

    async def handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle a single incoming connection."""
        self.connection_count += 1
        conn_id = self.connection_count

        # Get peer info
        peername = writer.get_extra_info('peername')
        sockname = writer.get_extra_info('sockname')

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"\n{'='*70}")
        print(f"[{timestamp}] CONNECTION #{conn_id} from {peername}")
        print(f"{'='*70}")

        try:
            # Read data with timeout
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(8192), timeout=5.0)
                except asyncio.TimeoutError:
                    print(f"[{conn_id}] Timeout waiting for data (5s)")
                    break

                if not data:
                    print(f"[{conn_id}] Connection closed by peer")
                    break

                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"\n[{timestamp}] [{conn_id}] Received {len(data)} bytes:")
                print(f"{'-'*50}")

                # Try to decode as text
                try:
                    text = data.decode('utf-8')
                    # Split headers and body for HTTP
                    if '\r\n\r\n' in text:
                        headers, body = text.split('\r\n\r\n', 1)
                        print("HEADERS:")
                        for line in headers.split('\r\n'):
                            print(f"  {line}")
                        if body:
                            print(f"\nBODY ({len(body)} bytes):")
                            print(f"  {body[:500]}")
                            if len(body) > 500:
                                print(f"  ... ({len(body) - 500} more bytes)")
                    else:
                        print(text[:1000])
                        if len(text) > 1000:
                            print(f"... ({len(text) - 1000} more bytes)")
                except UnicodeDecodeError:
                    # Show hex dump for binary data
                    print("BINARY DATA (hex):")
                    hex_dump = data[:256].hex()
                    for i in range(0, len(hex_dump), 32):
                        print(f"  {hex_dump[i:i+32]}")
                    if len(data) > 256:
                        print(f"  ... ({len(data) - 256} more bytes)")

                print(f"{'-'*50}")

                # Send a simple HTTP response
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    "Content-Length: 2\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    "[]"
                )
                writer.write(response.encode())
                await writer.drain()
                print(f"[{conn_id}] Sent 200 OK response")

        except Exception as e:
            print(f"[{conn_id}] Error: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            print(f"[{conn_id}] Connection closed")

    async def run(self):
        """Start the debug server."""
        server = await asyncio.start_server(
            self.handle_connection,
            self.host,
            self.port,
        )

        print(f"""
╔══════════════════════════════════════════════════════════════════════╗
║           HTTP Connection Debugger for Resonance                     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Listening on: {self.host}:{self.port:<5}                                        ║
║                                                                      ║
║  This tool helps debug why Squeezebox Boom/Touch devices             ║
║  aren't making HTTP/Cometd connections.                              ║
║                                                                      ║
║  Expected behavior:                                                  ║
║    1. Device sends UDP discovery broadcast                           ║
║    2. Server responds with TLV (IPAD, JSON port)                     ║
║    3. Device connects to HTTP port (this server)                     ║
║    4. Device sends POST /cometd with Bayeux handshake                ║
║                                                                      ║
║  If you see NO connections here but Discovery is working,            ║
║  the device might be:                                                ║
║    - Getting wrong IP in Discovery response                          ║
║    - Getting wrong port in Discovery response                        ║
║    - Having network routing issues                                   ║
║    - Failing to parse the Discovery response                         ║
║                                                                      ║
║  Press Ctrl+C to stop                                                ║
╚══════════════════════════════════════════════════════════════════════╝
""")

        async with server:
            await server.serve_forever()


async def also_run_discovery_logger():
    """Also listen for UDP discovery packets and log them."""
    print("Also starting UDP Discovery logger on port 3483...")

    class DiscoveryProtocol(asyncio.DatagramProtocol):
        def connection_made(self, transport):
            self.transport = transport
            print("UDP Discovery listener ready on port 3483")

        def datagram_received(self, data, addr):
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            if data and data[0:1] == b'e':
                # TLV discovery request
                print(f"\n[{timestamp}] 📡 UDP Discovery from {addr}")
                print(f"  Packet type: 'e' (TLV request)")

                # Parse TLV tags
                pos = 1
                tags = []
                while pos + 5 <= len(data):
                    tag = data[pos:pos+4].decode('ascii', errors='replace')
                    length = data[pos+4]
                    value = data[pos+5:pos+5+length] if length > 0 else b''
                    tags.append(tag)
                    if length > 0:
                        print(f"  - {tag}: {value.hex()}")
                    else:
                        print(f"  - {tag}: (requesting)")
                    pos += 5 + length

                print(f"  Tags requested: {', '.join(tags)}")

            elif data and data[0:1] == b'd':
                # Old-style discovery
                print(f"\n[{timestamp}] 📡 UDP Discovery from {addr}")
                print(f"  Packet type: 'd' (old-style)")
                if len(data) >= 18:
                    device_id = data[1]
                    revision = data[2]
                    mac = ':'.join(f'{b:02x}' for b in data[12:18])
                    print(f"  Device ID: {device_id}")
                    print(f"  Revision: {revision}")
                    print(f"  MAC: {mac}")

    loop = asyncio.get_event_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            DiscoveryProtocol,
            local_addr=("0.0.0.0", 3483),
            allow_broadcast=True,
        )
    except OSError as e:
        print(f"Could not bind UDP 3483 (probably already in use): {e}")
        print("Run this script INSTEAD of the server, not alongside it.")


async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000

    debugger = HTTPConnectionDebugger(port=port)

    # Try to also run the UDP discovery logger
    # (will fail if port is already in use)
    try:
        await also_run_discovery_logger()
    except Exception as e:
        print(f"Note: Could not start UDP logger: {e}")

    await debugger.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nStopped by user")
