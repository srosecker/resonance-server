# Resonance Deep Research – Squeezebox HTTP/Cometd Connection Problem (Touch-UI Devices)

> **Status note (2026-02-06):** This document is a **Markdown report stub** prepared for download.  
> It includes the structure, checklists, and extraction targets for the deep-dive.  
> It does **not yet** contain the final web-backed findings/citations (those require the completed research run).

## Scope (Priority)

Focus on:

1. **Connection sequence** (Discovery → Slimproto → HTTP/Cometd): ordering, dependencies, timing.
2. **HTTP/Cometd trigger** in SqueezePlay/Jive: what causes the first `/cometd` request.
3. **Touch-device Slimproto differences**: any special messages LMS sends to device IDs 8/9/10 that enable UI.

Secondary (if time permits):

- Hardware debugging methods (SSH/serial/hidden menus/logs).
- How non-touch devices (SB2/SB3/Classic/Transporter) differ (grfe/grfb etc.).

---

## 1) Step-by-step connection sequence (Expected)

### 1.1 Discovery (UDP 3483)
1. Device broadcasts discovery request (UDP 3483).
2. Server responds with TLVs (e.g., `IPAD`, `NAME`, `JSON`, `VERS`, `UUID`).
3. Touch-UI devices parse TLVs and create a `SlimServer` object; then call `server:updateAddress(ip, port, name)`.

**Your observation:** Discovery works; devices receive TLVs correctly.

### 1.2 Slimproto (TCP 3483)
4. Device opens TCP connection to server on port 3483.
5. Device sends `HELO` (contains device ID, MAC, firmware, etc.).
6. Server responds with initialization/feature/config commands (`vers`, `setd`, `aude`, `audg`, `strm q`, …).
7. Device starts sending `STAT` updates and performs audio streaming over HTTP (for playback).

**Your observation:** Works for audio subsystem; Squeezelite fully works.

### 1.3 HTTP/Cometd (TCP 9000)
8. Touch-UI (SqueezePlay/Jive) opens HTTP connection to server on port 9000.
9. Performs **Cometd/Bayeux handshake** via HTTP POST to `/cometd` (or configured endpoint).
10. Establishes long-poll/streaming connection (depending on `supportedConnectionTypes`).
11. Uses JSON-RPC / menu APIs to populate UI; server pushes updates via Cometd.

**Your observation:** Step 8 never happens (no connection to 9000).

---

## 2) What triggers HTTP/Cometd (Hypothesis matrix)

### 2.1 Where the trigger seems to live (from your code excerpts)
- `SlimDiscoveryApplet.lua` calls `_serverUpdateAddress(...)` after TLV parsing.
- `_serverUpdateAddress` calls `server:updateAddress(ip, port, name)` then `server:connect()` in certain states.
- `SlimServer.lua:updateAddress` sets Comet endpoint `self.comet:setEndpoint(ip, port, '/cometd')`.
- `SlimServer.lua:connect` calls `self.comet:connect()`.
- `Comet.lua:connect()` calls `_handshake(self)` → expected HTTP POST to `/cometd`.

**Key implication:** if Discovery code runs and the state machine reaches `server:connect()`, the UI should attempt `/cometd` regardless of Slimproto (unless blocked by state/feature checks).

### 2.2 Possible “gating” conditions to verify
These are the highest-probability places where the HTTP attempt could be skipped:

- **Discovery state machine**: `self.state` not in `searching/probing_player/probing_server`.
- **Server port**: `port` extracted from TLVs isn’t 9000 (or not present), or `updateAddress` gets a wrong/empty port.
- **Endpoint scheme**: HTTP vs HTTPS assumptions; proxy env; DNS mismatch; or IPv6 parsing.
- **Network policy**: UI process doesn’t have outbound to 9000 (firewall/VLAN), while slimproto 3483 works.
- **Feature/compat gating**: device decides Resonance is not “LMS-like enough” (e.g., missing headers, wrong JSON TLV, version fields).
- **Slimproto handshake gating**: UI waits for player registration/identity from 3483 before enabling Cometd.

### 2.3 Practical checks you can do immediately
1. **On the server:** run a listener on 9000 and log SYNs (even rejected) to confirm no TCP attempt happens.
2. **On the device:** if possible, enable debug logs for SqueezePlay/Jive and look for `Comet: connect` / handshake lines.
3. **On the wire:** compare LMS vs Resonance discovery responses byte-for-byte (TLV order/length too).
4. **On Resonance:** add verbose logging for discovery response payload and exact `JSON` TLV content.

---

## 3) Slimproto messages that may be special for Touch-UI devices (What to research)

### 3.1 Candidate messages / behaviors
- Additional `setd` flags (e.g., `setd 0x04`) used by Boom/Radio/Touch to control display, brightness, UI integration, or capabilities.
- Any `serv`/`resp`/`msgs` that advertise the HTTP server URL/port or JSON endpoints.
- Player “registration complete” events that might unblock UI startup.

### 3.2 Compare LMS traces for Touch vs non-touch
Collect in Wireshark (TCP 3483) for:
- Squeezebox Radio/Boom/Touch vs Squeezebox Classic/Transporter
- Look for additional server→device messages after `HELO` beyond the common set.

---

## 4) Required code excerpt targets (to paste once extracted)

> Paste relevant minimal excerpts here (≤ ~100–200 lines per file), focusing on:
> TLV composition, how HTTP port is encoded, how Jive is notified, and Cometd handshake implementation.

### 4.1 `Slim/Networking/Discovery/Server.pm` (targets)
- How the discovery response TLVs are built
- Which TLVs are included for Touch devices vs others
- How the **HTTP/JSON port** is conveyed (9000, possibly configurable)
- Any device-ID conditional logic (`baby`, `boom`, `jive`, etc.)

```text
[TBD – paste excerpt]
```

### 4.2 `Slim/Web/Cometd.pm` (targets)
- Handshake response fields
- `supportedConnectionTypes`
- Advice fields (`timeout`, `reconnect`, etc.)
- Any auth/session cookie requirements
- Path routing: `/cometd` vs `/cometd/…`

```text
[TBD – paste excerpt]
```

### 4.3 JiveLite `SlimDiscoveryApplet.lua` (targets)
- TLV parsing logic
- State machine (`searching`, `probing_player`, etc.)
- Condition for calling `server:connect()`

```text
[TBD – paste excerpt]
```

### 4.4 JiveLite `Comet.lua` (targets)
- `_handshake` implementation
- HTTP request formation (headers, content-type, JSON body)
- Connection types (long-polling vs streaming)
- Error backoff behavior (silent failure?)

```text
[TBD – paste excerpt]
```

---

## 5) Alternative implementations (to populate)

Goal: find **verified** implementations that support Touch-UI devices (Cometd/Jive):

- *Candidate list* (TBD after research):
  - LMS forks (Lyrion / LMS-Community variants)
  - Minimal servers/proxies that implement Cometd + slimproto
  - Emulators/simulators

```text
[TBD – links and summary]
```

---

## 6) Hardware debugging ideas (secondary)

- Hidden debug menus for Squeezebox Radio/Boom/Touch
- Serial console header / UART logging
- Firmware extraction / SSH (if available on certain firmware builds)
- Log file locations for SqueezePlay/Jive (if exposed)

```text
[TBD – step-by-step per device]
```

---

## Appendix A – Your observed “works vs fails” matrix

| Subsystem | Port | Status | Notes |
|---|---:|---|---|
| Discovery | UDP 3483 | ✅ Works | TLVs received (IPAD/NAME/JSON/VERS/UUID) |
| Slimproto | TCP 3483 | ✅ Works | `HELO`, then `vers/strm q/setd/aude/audg` |
| HTTP/Cometd | TCP 9000 | ❌ Fails | No connection attempt observed |

---

## Appendix B – Immediate “most likely” root causes shortlist

1. **Discovery TLV subtle mismatch** (ordering/length/port field) causes Jive not to call `server:connect()`.
2. **Port mismatch**: Jive learns wrong UI port (not 9000) and never tries.
3. **State machine not in connectable state** (`SlimDiscoveryApplet` state gating).
4. **Feature/version compatibility**: Jive rejects server if version/capabilities don’t match expected LMS semantics.
5. **Network policy**: device can reach 3483 but not 9000 due to firewall/VLAN rules.

---

## Appendix C – Data to capture for the final report

- Discovery response bytes from LMS vs Resonance (pcap + hexdump)
- First 20 seconds of TCP 3483 exchange after HELO (both servers)
- Any DNS/HTTP attempts to cover art URLs (could indicate UI is partially alive)
- Device firmware version and whether it can browse “My Music” on a real LMS
