# Deep Research: Squeezebox HTTP/Cometd Connection Problem

## Context

We are developing **Resonance**, a Python reimplementation of the Logitech Media Server (LMS/SlimServer). The goal is full compatibility with all Squeezebox hardware devices.

### Target Devices

| Device | Device ID | Display | Touch-UI (Jive/SqueezePlay) | Status |
|--------|-----------|---------|----------------------------|--------|
| SLIMP3 | 1 | Neon | No | Untested |
| Squeezebox 2 | 2 | VFD | No | Untested |
| Squeezebox 3 | 3 | VFD | No | Untested |
| Squeezebox Classic | 4 | VFD | No | Untested |
| Transporter | 5 | VFD | No | Untested |
| Squeezebox Receiver | 7 | None | No | Untested |
| Squeezebox Touch | 8 | LCD | Yes (SqueezePlay) | Untested |
| Squeezebox Controller | 9 | LCD | Yes (SqueezePlay) | ❌ No HTTP |
| Squeezebox Boom | 10 | LCD | Yes (SqueezePlay) | ❌ No HTTP |
| Squeezebox Radio | 9 (baby) | LCD | Yes (SqueezePlay) | ❌ No HTTP |
| Squeezelite (Software) | 12 | None | No | ✅ Works |

### What Works

- ✅ **UDP Discovery** (Port 3483) — Devices receive TLVs correctly (IPAD, NAME, JSON, VERS, UUID)
- ✅ **Slimproto TCP** (Port 3483) — Devices connect, send HELO, receive server commands
- ✅ **Server Responses** — `vers`, `strm q`, `setd`, `aude`, `audg` are sent correctly
- ✅ **Squeezelite** (Software player) works fully with streaming and playback

### The Problem

**Squeezebox devices with Touch-UI (Boom, Radio, Touch, Controller) do NOT make an HTTP/Cometd connection to port 9000!**

The devices:
1. Send Discovery requests → Receive correct TLV responses ✅
2. Connect via Slimproto TCP → Send HELO, receive commands ✅
3. **Never make an HTTP connection to port 9000** ❌

Without the Cometd connection, the Touch-UI (Jive/SqueezePlay) cannot function — no menus, no controls, no library browsing.

---

## Architecture Overview

### LMS Communication Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Logitech Media Server (LMS)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐    ┌────────────┐    ┌────────────────┐         │
│  │  Discovery │    │  Slimproto │    │  HTTP/Cometd   │         │
│  │ UDP :3483  │    │ TCP :3483  │    │   TCP :9000    │         │
│  └────────────┘    └────────────┘    └────────────────┘         │
│        │                 │                   │                   │
└────────┼─────────────────┼───────────────────┼───────────────────┘
         │                 │                   │
         ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Squeezebox Hardware                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                 Audio Firmware (Player)                    │  │
│  │  - Receives Slimproto commands (strm, audg, etc.)         │  │
│  │  - Streams audio via HTTP                                  │  │
│  │  - Sends status (STAT) back to server                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │          SqueezePlay/Jive (Touch-UI) - Touch devices only │  │
│  │  - Lua-based UI application                                │  │
│  │  - Communicates via Cometd/Bayeux (HTTP streaming)        │  │
│  │  - Shows menus, cover art, now playing                    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Two Separate Subsystems

1. **Player Subsystem (Slimproto)**
   - Binary protocol on TCP port 3483
   - Controls audio playback
   - Works in our implementation ✅

2. **UI Subsystem (Cometd/HTTP)**
   - JSON-RPC over HTTP port 9000
   - Bayeux/Cometd for real-time updates
   - Controls Touch-UI, menus, browsing
   - **Does NOT work in our implementation** ❌

---

## Our Analysis

### Wireshark Captures

We analyzed network traffic between Squeezebox Radio/Boom and our Resonance server:

| Observation | Details |
|-------------|---------|
| Discovery | Radio sends broadcast, receives TLVs ✅ |
| Slimproto | TCP connection to port 3483 ✅ |
| HELO | Radio sends HELO with Device ID 9 ✅ |
| Server Response | `vers`, `strm q`, `setd`, `aude`, `audg` ✅ |
| HTTP to port 9000 | **NO connection!** ❌ |

### Comparison: LMS vs Resonance

| Aspect | LMS | Resonance |
|--------|-----|-----------|
| UUID Format | 36 chars (UUID v4) | ✅ 36 chars |
| Discovery TLVs | IPAD, NAME, JSON, VERS, UUID | ✅ Identical |
| Slimproto after HELO | `strm q`, `setd 0x00`, `setd 0x04`, `aude`, `audg` | ✅ Identical |
| HTTP Connection | Established | ❌ Not established |

---

## Relevant Code

### JiveLite/SqueezePlay Discovery (Lua)

```lua
-- SlimDiscoveryApplet.lua
local function _slimDiscoverySink(self, chunk, err)
    -- Parse TLVs from Discovery response
    local name, ip, port, version, uuid = nil, chunk.ip, nil, nil, nil
    
    -- TLV parsing loop...
    
    if name and ip and port then
        local server = SlimServer(jnt, uuid, name, version)
        self:_serverUpdateAddress(server, ip, port, name)
    end
end

function _serverUpdateAddress(self, server, ip, port, name)
    server:updateAddress(ip, port, name)
    
    if self.state == 'searching'
        or self.state == 'probing_player'
        or self.state == 'probing_server' then
        server:connect()  -- Should trigger Cometd connection!
    end
end
```

### SlimServer.lua

```lua
function updateAddress(self, ip, port, name)
    -- ...
    self.comet:setEndpoint(ip, port, '/cometd')
    
    if oldstate ~= 'disconnected' then
        self:connect()
    end
end

function connect(self)
    self.comet:connect()  -- Starts Cometd handshake
end
```

### Comet.lua (Cometd Client)

```lua
function connect(self)
    self.isactive = true
    
    if self.state == CONNECTING or self.state == CONNECTED then
        return  -- Already connecting
    end
    
    _state(self, CONNECTING)
    _handshake(self)  -- HTTP POST to /cometd
end
```

---

## Research Questions

### 1. Connection Sequence

**Question:** What is the exact order in which a Squeezebox device establishes all connections?

- Discovery → Slimproto → HTTP? Or parallel?
- Are there dependencies between connections?
- Must the player be "registered" via Slimproto before HTTP works?

### 2. HTTP Connection Trigger

**Question:** What exactly triggers SqueezePlay/Jive to establish an HTTP connection?

- Is it purely Discovery-based?
- Does it need a Slimproto event from the server?
- What role does the SlimDiscoveryApplet `state` play?

### 3. JVID TLV in Discovery

**Question:** What is the role of the JVID TLV in the Discovery request?

```lua
'JVID', string.char(0x06, 0x12, 0x34, 0x56, 0x78, 0x12, 0x34)
```

- Is this the MAC address of the Jive controller?
- Does LMS expect a specific response?
- Must we echo JVID back in the response?

### 4. Slimproto Messages for Touch Devices

**Question:** Does LMS send special Slimproto messages to Touch devices?

- Is there a "UI-Ready" or "Connect-HTTP" command?
- Does the sequence differ for Touch vs Non-Touch devices?
- What is the meaning of `setd 0x04`?

### 5. Firmware Versions and Compatibility

**Question:** Are there documented firmware dependencies?

- Minimum LMS version for certain hardware?
- Firmware updates that change HTTP behavior?
- Known bugs in older firmware versions?

### 6. JSON-RPC Port Discovery

**Question:** How does SqueezePlay learn the HTTP port?

- From the JSON TLV in Discovery?
- From a Slimproto message?
- Hardcoded to 9000?

### 7. Cometd Handshake Requirements

**Question:** What does SqueezePlay expect from the Cometd handshake?

- Special response fields?
- Required `supportedConnectionTypes`?
- Specific `advice` parameters?

### 8. Display Devices Without Touch-UI

**Question:** How do Squeezebox 2/3, Classic, Transporter work?

- Do they also use HTTP communication?
- Or only Slimproto for everything (including display updates)?
- What is the `grfe`/`grfb` protocol for VFD/LCD?

### 9. Alternative Server Implementations

**Question:** Are there other successful LMS reimplementations?

- How did they solve this problem?
- Open-source projects to reference?
- Documented compatibility issues?

### 10. Hardware Debugging

**Question:** How can we get debug information from the Squeezebox?

- SSH access to firmware?
- Hidden debug menus?
- Serial console?
- Log files on the device?

---

## Search Terms

### General
- "squeezebox server implementation"
- "squeezebox protocol documentation"
- "logitech media server alternative"
- "slimproto protocol specification"
- "squeezebox cometd bayeux"

### Specific
- "squeezebox touch not connecting"
- "squeezebox radio http connection"
- "squeezebox boom server compatibility"
- "squeezeplay jive http"
- "LMS cometd handshake"

### Technical
- `Slim::Networking::Discovery`
- `Slim::Web::Cometd`
- `Slim::Player::Squeezebox2`
- `jive.net.Comet`
- `SlimDiscoveryApplet`
- `slimproto HELO STAT STRM`

### Forums/Communities
- forums.slimdevices.com
- community.lyrion.org
- github.com/LMS-Community
- reddit.com/r/squeezebox

---

## Relevant Source Code Files

### LMS (Perl)
- `Slim/Networking/Discovery/Server.pm` — Discovery handler
- `Slim/Web/Cometd.pm` — Cometd/Bayeux implementation
- `Slim/Player/Squeezebox.pm` — Base player class
- `Slim/Player/Squeezebox2.pm` — SB2/SB3 specific
- `Slim/Player/Boom.pm` — Boom specific
- `Slim/Player/Baby.pm` — Radio specific
- `Slim/Control/Jive.pm` — Jive menu system
- `Slim/Control/Commands.pm` — CLI commands

### JiveLite/SqueezePlay (Lua)
- `share/jive/applets/SlimDiscovery/SlimDiscoveryApplet.lua`
- `share/jive/jive/slim/SlimServer.lua`
- `share/jive/jive/net/Comet.lua`
- `share/jive/jive/net/SocketHttp.lua`
- `share/jive/jive/net/SocketTcp.lua`

---

## Hypotheses

1. **Missing Slimproto message**: LMS sends a command after HELO that triggers HTTP
2. **State machine problem**: SqueezePlay's `state` is not `searching`
3. **Incomplete Discovery response**: A TLV is missing or malformed
4. **Timing problem**: HTTP attempt happens before our server is ready
5. **Firewall/Network**: Outgoing connection from Squeezebox is blocked
6. **Firmware incompatibility**: Old firmware expects something specific

---

## Desired Answers

1. **Complete connection sequence** — Step by step what must happen
2. **Trigger condition** — What exactly triggers the HTTP connection?
3. **Differences between devices** — Touch vs Non-Touch, different models
4. **Reference implementations** — Working alternatives to LMS
5. **Debug methods** — How to see what's happening on the Squeezebox
6. **Known issues** — Documented compatibility problems and solutions