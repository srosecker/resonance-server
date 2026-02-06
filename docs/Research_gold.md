# Why Squeezebox Touch-UI devices won't HTTP-connect to your server

**The HTTP/Cometd connection is triggered entirely by UDP Discovery parsing—not by Slimproto—and the most probable failure points are the JSON TLV port encoding, a missing or malformed UUID TLV, or a version string that triggers firmware rejection.** Touch-UI devices (Boom, Radio, Touch, Controller) run SqueezePlay, which uses two independent connection paths: Slimproto TCP for audio control and HTTP/Cometd for UI menus. These are established in parallel, not sequentially. Squeezelite works because it only needs Slimproto; hardware devices additionally require a fully functioning Cometd server discovered via specific TLV values in UDP responses. No alternative LMS reimplementation has ever solved this problem—LMS remains the only server with working Touch-UI Cometd support.

---

## The complete connection sequence is parallel, not serial

Touch-UI devices establish three independent connections that run concurrently, each triggered by different mechanisms. Understanding this architecture is critical because the HTTP connection failure is almost certainly a Discovery-layer problem, not a Slimproto-layer problem.

**UDP Discovery (port 3483 broadcast)** happens first. The device broadcasts an `e`-type TLV packet every **10 seconds** while in `searching` state. When a valid response arrives, `_slimDiscoverySink` in `SlimDiscoveryApplet.lua` parses the TLVs, creates a `SlimServer` object (keyed by UUID), and immediately calls `server:connect()`, which initiates the Cometd HTTP connection. This happens entirely independently of Slimproto.

**Slimproto TCP (port 3483)** is established separately by the `SlimProto.lua` module. The device connects, sends HELO, and begins the audio-control handshake. On hardware devices, the local player component manages this connection independently from the discovery/UI layer.

**HTTP/Cometd (port from JSON TLV)** is triggered by `_serverUpdateAddress()` calling `server:connect()` after discovery response parsing. The `SlimServer:connect()` method creates a `Comet` object targeting `http://<ip>:<json_port>/cometd` and initiates the Bayeux handshake. **There is no dependency on Slimproto being connected first for the Cometd connection to be attempted.** However, once connected, Cometd requests that reference a player MAC will fail with `errorNeedsClient` if that player hasn't completed Slimproto registration.

The discovery state machine has five states: `disconnected`, `searching`, `probing_player`, `probing_server`, and `connected`. The `server:connect()` call only fires when the state is `searching`, `probing_player`, or `probing_server`—not when `connected` or `disconnected`. On boot, hardware devices enter `searching` after network initialization.

---

## Discovery response format is where your bug most likely lives

The TLV format is deceptively simple but unforgiving. Each TLV in both request and response follows this exact byte layout:

```
[4 bytes: ASCII tag] [1 byte: value length] [N bytes: value]
```

The response packet starts with a single byte `E` (0x45), followed by concatenated TLVs. Here is an actual 74-byte wire capture of a working LMS response:

```
0x45                                    -- 'E' response type
"NAME" 0x08 "MacMini2"                  -- server name (8 bytes)
"JSON" 0x04 "9500"                      -- HTTP port as ASCII STRING (4 bytes)
"VERS" 0x05 "7.9.0"                     -- server version (5 bytes)
"UUID" 0x24 "75ab0441-2381-4093-..."    -- 36-char UUID with dashes
```

**The JSON TLV value must be the port number as an ASCII string** (e.g., `"9000"`)—not a 2-byte big-endian integer, not a JSON object, not binary. The misleading tag name "JSON" refers to the JSON-RPC service port, but the value encoding is plain ASCII text. The client-side parsing in `_slimDiscoverySink` reads it as a Lua string via `chunk.data:sub(ptr + 5, ptr + 4 + l)`. If you're encoding the port as a binary integer or a JSON object like `{"httpport": 9000}`, the client will fail silently.

**The UUID TLV is absolutely required.** The `_slimDiscoverySink` function contains this critical gate:

```lua
if uuid then
    local server = SlimServer:getServerByUuid(uuid)
    if not server then
        server = SlimServer(jnt, uuid, name, version)
    end
    self:_serverUpdateAddress(server, ip, port, name)
end
```

If `uuid` is `nil`—because the UUID TLV is missing, has zero length, or the tag is misspelled—no `SlimServer` object is created and `connect()` is never called. The UUID format should be the standard **36-character string with dashes** (e.g., `"75ab0441-2381-4093-a814-0fc6f05ede7b"`).

**The IPAD TLV is optional.** The client extracts the server IP from the UDP packet's source address (`chunk.ip`), so IPAD is only needed if you want to override that. LMS only returns IPAD if explicitly configured.

**JVID is sent by the client, not echoed by the server.** The client sends `JVID` with a 6-byte value (MAC-like identifier) in the discovery request. The original SqueezePlay source has a telling comment: `JVID', string.char(0x06, 0x12, 0x34, 0x56, 0x78, 0x12, 0x34), -- My ID - FIXME mac of no use!`. The server does **not** need to respond with a JVID TLV. You can safely ignore it.

---

## The VERS TLV can silently kill compatibility

SqueezePlay firmware versions 7.7.3 and earlier contain a **version string comparison bug** that causes them to reject servers reporting version 8.0.0 or higher. The firmware performs a naïve string comparison where `"8.0.0" < "7.9.0"` because `'7' > '8'` is false in simple character comparison, but the multi-segment comparison logic fails on the major version boundary.

LMS works around this with `Slim::Networking::Discovery::getFakeVersion()`, which returns **"7.9.1"** to devices running affected firmware. The detection happens when a `serverstatus` query's user-agent matches `SqueezePlay-(baby|fab4|jive|squeezeplay)` without the `-lms8` patch indicator.

**For Resonance, the VERS TLV in discovery responses should return a version string in the 7.x range** (e.g., "7.9.1") unless you're certain all devices have the community firmware patch. If you're returning something like "1.0.0" or "0.0.1", the firmware's version comparison might also reject or mishandle it—stick with `"7.9.1"` to be safe.

---

## The Cometd handshake has non-standard requirements

SqueezePlay's `Comet.lua` initiates the Bayeux handshake with specific expectations that deviate from the standard spec. The iPeng developer explicitly warned: **"Don't expect Logitech's cometd implementation to conform to the Bayeux Spec."**

The handshake request from SqueezePlay looks exactly like this:

```json
[{
  "channel": "/meta/handshake",
  "version": "1.0",
  "supportedConnectionTypes": ["streaming"],
  "ext": {
    "rev": "7.7.1 r0",
    "uuid": "deb5cee74630d6ece2e1c0cf52dd1cdd",
    "mac": "00:04:20:23:a7:6d"
  }
}]
```

Note that SqueezePlay requests **"streaming" only**—not "long-polling". The server must respond with a `supportedConnectionTypes` array that includes `"streaming"`. A correct handshake response is:

```json
[{
  "clientId": "f81854d3",
  "supportedConnectionTypes": ["long-polling", "streaming"],
  "version": "1.0",
  "channel": "/meta/handshake",
  "advice": {
    "timeout": 60000,
    "interval": 0,
    "reconnect": "retry"
  },
  "successful": true
}]
```

Critical response fields: **`clientId`** (8-character hex string), **`successful: true`**, and **`advice`** with `reconnect: "retry"`, `timeout: 60000`, `interval: 0`. LMS notably does **not** return an `id` field in handshake responses—this is non-standard and some Bayeux libraries may complain. The response Content-Type must be `application/json`.

After handshake, the client sends a combined `/meta/connect` + `/meta/subscribe` request:

```json
[{
  "channel": "/meta/connect",
  "clientId": "f81854d3",
  "connectionType": "streaming"
}, {
  "channel": "/meta/subscribe",
  "clientId": "f81854d3",
  "subscription": "/f81854d3/**"
}]
```

This `chttp` connection then stays open as a long-lived HTTP response for server-pushed events. Subsequent command requests go through a separate `rhttp` connection.

After subscribing, the first meaningful request is typically a `serverstatus` query via `/slim/request`, which lists available players. The custom `/slim/request` and `/slim/subscribe` channels (not standard Bayeux) are how all LMS commands flow.

---

## Slimproto messages after HELO and what setd actually means

When a Touch-UI device sends HELO, the LMS server responds with this observed sequence:

```
Device → Server:  HELO (device_id=12, Model=fab4, ModelName=Squeezebox Touch, ...)
Server → Device:  strm (28 bytes, command='q' — stop/flush)
Device → Server:  STAT (status response)
Server → Device:  setd (5 bytes, id=0x00 — query player name)
Device → Server:  SETD (responds with id byte + player name string)
Device → Server:  STAT
Server → Device:  setd (5 bytes, id=0x00 — second setd, possibly server address)
Device → Server:  SETD (response)
Server → Device:  aude (audio enable: spdif + dac flags)
Server → Device:  audg (audio gain/volume)
Server → Device:  vers (server version string)
Server → Device:  strm 't' (periodic timing/status request, every ~5 seconds)
```

**The `setd` command with id=0x00 queries the player name.** The packet is 5 bytes after the 8-byte header: 1 byte id (0x00) + 4 bytes data. When the data is empty or zero, it's a query; when populated, it's a set. The SqueezePlay handler in `Playback.lua` confirms this:

```lua
function _setd(self, data)
    if data.command == 0 and #data.packet <= 5 then
        local player = Player:getLocalPlayer()
        self.slimproto:send({
            opcode = 'SETD',
            data = table.concat({ string.sub(data.packet, 5, 5), player:getName() })
        })
    end
end
```

**The `setd 0x04` mystery**: Despite the `_http_setting_handler` comment in `slimproto.h`, squeezelite's `process_setd` only handles id=0 (player name). The squeezelite client ignores id=0x04 entirely. On the server side, the comment appears to be the name of the Perl subroutine that processes incoming SETD messages, not a description of what id=0x04 does. The actual HTTP port communication happens through the **JSON TLV in Discovery**, not through Slimproto setd commands. There is **no "HTTP ready" or "connect now" signal** sent via Slimproto to trigger the Cometd connection.

**Critical for connection stability**: The server must send periodic `strm 't'` (timing/status request) messages every ~5 seconds. SqueezePlay has a **35-second inactivity timeout** on the Slimproto connection. If no messages arrive within that window, the device considers the connection dead, logs `"No messages from server - connection dead"`, disconnects, and attempts to reconnect. This causes a reconnection loop that can interfere with the overall device stability, even though it shouldn't directly prevent the initial Cometd connection attempt.

---

## Most likely root causes for Resonance, ranked by probability

Based on all evidence, here are the most probable reasons Touch-UI devices are not making the HTTP connection, ordered by likelihood:

- **The JSON TLV value is not an ASCII string.** If you're encoding port 9000 as two binary bytes (`\x23\x28`) or as a JSON object, the client's Lua string parsing will produce garbage or nil. The value must be the literal characters `"9000"` (4 bytes, length byte = 0x04).

- **The UUID TLV is missing or malformed.** Without a valid UUID string in the response, the `if uuid then` gate in `_slimDiscoverySink` prevents server object creation entirely. The UUID must be a 36-character string with dashes in the standard format.

- **The VERS TLV triggers version rejection.** If your server returns a version like "0.1.0" or "8.0.0" or "9.0.0", the firmware's buggy version comparison may silently refuse to connect. Use **"7.9.1"** as the version string.

- **The discovery response has TLV encoding errors.** Even one incorrect length byte, missing length byte, or wrong tag capitalization will cause the parsing loop to desynchronize and skip all subsequent TLVs. Verify byte-by-byte against the format: `[4-char TAG][1-byte length][N-byte value]`.

- **The HTTP server doesn't handle streaming Cometd correctly.** If your `/cometd` endpoint doesn't keep the HTTP connection open (true streaming), or returns `supportedConnectionTypes: ["long-polling"]` without `"streaming"`, the Comet state machine may fail during handshake.

---

## How to debug this on the actual hardware

**Enable SSH on Squeezebox devices** via Settings → Advanced → Remote Login → Enable SSH. On devices stuck in setup, a hidden developer menu appears when you press both "Home" and ">>" (forward) simultaneously. The default root password is **`1234`**. Modern SSH clients need legacy cipher options:

```bash
ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -c aes256-cbc \
    -oHostKeyAlgorithms=+ssh-dss -l root <device-ip>
```

**Enable SqueezePlay debug logging** by creating a `logconf.lua` file or editing the log configuration to set these categories to DEBUG:

- `net.comet` — Cometd connection state, handshake, subscriptions
- `net.slimproto` — Slimproto message exchange
- `applet.SlimDiscovery` — Discovery state machine, server creation
- `slimserver` — Server connection state changes

On the LMS/server side, enable `network.cometd` debug logging in Settings → Advanced → Logging to see all incoming Cometd requests and any `errorNeedsClient` failures.

**The fastest diagnostic approach**: SSH into the device and `tail -f /var/log/messages` while it attempts to connect. Look for these specific log patterns:

- `SlimDiscoveryApplet` messages showing whether discovery responses are being parsed
- `SlimServer.lua: address set to <ip>:<port>` confirming the server was created
- `Comet: _handshake` showing whether the HTTP connection is even attempted
- `NetworkThread.lua: network thread timeout` indicating connection timeouts
- Any error messages from the Comet or SlimServer modules

## Conclusion

The root cause almost certainly lies in the Discovery response TLV encoding—specifically the JSON port format, UUID presence, or version string compatibility—not in the Slimproto layer. The Cometd connection is triggered independently by Discovery and does not wait for Slimproto. Verify your TLV byte layout character by character against the format documented above, set VERS to "7.9.1", ensure UUID is a 36-character dashed string, and confirm JSON contains the port as an ASCII string. No other LMS reimplementation has ever achieved Touch-UI Cometd compatibility, making this genuinely uncharted territory for the open-source community. Once discovery triggers the connection attempt, focus shifts to ensuring `/cometd` supports streaming connection types and responds with all required Bayeux fields including `clientId`, `successful`, and `advice`.