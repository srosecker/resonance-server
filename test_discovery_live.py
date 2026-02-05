"""Live UDP Discovery Test Script.

Tests whether the Resonance server responds to UDP discovery requests.
Run the server first, then run this script.
"""

import socket
import struct
import sys


def test_old_style_discovery(host: str = "127.0.0.1", port: int = 3483) -> bool:
    """Test old-style 'd' discovery (SLIMP3/Squeezebox)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    # Old-style discovery: 'd' + 17 zero bytes = 18 bytes total
    discovery_packet = b"d" + b"\x00" * 17

    print(f"Testing old-style 'd' discovery to {host}:{port}...")
    try:
        sock.sendto(discovery_packet, (host, port))
        response, addr = sock.recvfrom(1024)
        print(f"  Response from {addr}: {len(response)} bytes")
        print(f"  Packet type: {chr(response[0])!r}")

        if response[0] == ord("D"):
            # Parse response: 'D' + hostname (256 bytes padded)
            hostname = response[1:257].rstrip(b"\x00").decode("utf-8", errors="replace")
            print(f"  Server hostname: {hostname}")
            print("  ✅ Old-style discovery works!")
            return True
        else:
            print(f"  ❌ Unexpected response type: {chr(response[0])!r}")
            return False

    except socket.timeout:
        print("  ❌ Timeout - Server not running or not responding")
        return False
    except ConnectionRefusedError:
        print("  ❌ Connection refused - Server probably not running")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        sock.close()


def test_tlv_discovery(host: str = "127.0.0.1", port: int = 3483) -> bool:
    """Test TLV-style 'e' discovery (newer players)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    # TLV discovery: 'e' + TLV entries
    # Request NAME (0x4e414d45) with length 0
    tlv_name = b"NAME" + b"\x00"
    discovery_packet = b"e" + tlv_name

    print(f"\nTesting TLV-style 'e' discovery to {host}:{port}...")
    try:
        sock.sendto(discovery_packet, (host, port))
        response, addr = sock.recvfrom(1024)
        print(f"  Response from {addr}: {len(response)} bytes")
        print(f"  Packet type: {chr(response[0])!r}")

        if response[0] == ord("E"):
            print(f"  Raw TLV data: {response[1:].hex()}")
            # Parse TLV entries
            data = response[1:]
            pos = 0
            while pos + 5 <= len(data):
                tag = data[pos:pos+4].decode("ascii", errors="replace")
                length = data[pos+4]
                value = data[pos+5:pos+5+length]
                print(f"  TLV: {tag} = {value!r}")
                pos += 5 + length
            print("  ✅ TLV-style discovery works!")
            return True
        else:
            print(f"  ❌ Unexpected response type: {chr(response[0])!r}")
            return False

    except socket.timeout:
        print("  ❌ Timeout - Server not running or not responding")
        return False
    except ConnectionRefusedError:
        print("  ❌ Connection refused - Server probably not running")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        sock.close()


def test_broadcast_discovery(port: int = 3483) -> bool:
    """Test broadcast discovery (like real Squeezebox Radio does)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # TLV discovery with all fields a Radio requests
    # 'e' + IPAD + NAME + JSON + VERS + UUID + JVID
    discovery_packet = b"e"
    discovery_packet += b"IPAD\x00"  # Request IP
    discovery_packet += b"NAME\x00"  # Request name
    discovery_packet += b"JSON\x00"  # Request JSON port
    discovery_packet += b"VERS\x00"  # Request version
    discovery_packet += b"UUID\x00"  # Request UUID

    print(f"\nTesting BROADCAST discovery to 255.255.255.255:{port}...")
    try:
        sock.sendto(discovery_packet, ("255.255.255.255", port))
        response, addr = sock.recvfrom(1024)
        print(f"  Response from {addr}: {len(response)} bytes")
        print(f"  Packet type: {chr(response[0])!r}")

        if response[0] == ord("E"):
            # Parse TLV entries
            data = response[1:]
            pos = 0
            while pos + 5 <= len(data):
                tag = data[pos:pos+4].decode("ascii", errors="replace")
                length = data[pos+4]
                value = data[pos+5:pos+5+length]
                print(f"  TLV: {tag} = {value.decode('utf-8', errors='replace')!r}")
                pos += 5 + length
            print("  ✅ Broadcast discovery works!")
            return True
        else:
            print(f"  ❌ Unexpected response type: {chr(response[0])!r}")
            return False

    except socket.timeout:
        print("  ❌ Timeout - No server responded to broadcast")
        return False
    except PermissionError:
        print("  ❌ Permission denied - may need admin rights for broadcast")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        sock.close()


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3483

    print("=" * 60)
    print("UDP Discovery Live Test")
    print("=" * 60)
    print(f"Target: {host}:{port}")
    print()

    old_ok = test_old_style_discovery(host, port)
    tlv_ok = test_tlv_discovery(host, port)
    broadcast_ok = test_broadcast_discovery(port)

    print()
    print("=" * 60)
    print("Summary:")
    print(f"  Old-style ('d'):    {'✅ PASS' if old_ok else '❌ FAIL'}")
    print(f"  TLV-style ('e'):    {'✅ PASS' if tlv_ok else '❌ FAIL'}")
    print(f"  Broadcast ('e'):    {'✅ PASS' if broadcast_ok else '❌ FAIL'}")
    print("=" * 60)

    return 0 if (old_ok and tlv_ok and broadcast_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
