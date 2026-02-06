# SqueezePlay internals: four barriers between discovery and Cometd

**The `'connected'` state in SlimDiscoveryApplet is the primary gating mechanism** that suppresses `server:connect()` calls for newly discovered servers. When a device is already connected to any server — including mysqueezebox.com (SqueezeNetwork) — the function `_serverUpdateAddress()` explicitly skips the `server:connect()` call, meaning a Resonance server's discovery response will update the server list but never trigger a Cometd connection. This behavior compounds with three other barriers: the mandatory setup wizard on original firmware, hardware-specific gating absent from JiveLite, and UDAP traffic on port 17784 that is unrelated to Cometd but may cause diagnostic confusion.

---

## The state machine has exactly five states and one critical gate

SlimDiscoveryApplet operates with five states: `'disconnected'`, `'searching'`, `'probing_player'`, `'probing_server'`, and `'connected'`. The central gating function is `_serverUpdateAddress()`, which is **identical across all three source repositories** (ralph-irving/squeezeplay, LMS-Community/squeezeplay, triode-jivelite):

```lua
function _serverUpdateAddress(self, server, ip, port, name)
    server:updateAddress(ip, port, name)

    if self.state == 'searching'
        or self.state == 'probing_player'
        or self.state == 'probing_server' then
        server:connect()
    end
end
```

This function **always** calls `server:updateAddress()` to update metadata, but only calls `server:connect()` in three states. When the state is `'connected'` or `'disconnected'`, the connect call is suppressed entirely. This is the precise mechanism that prevents a Resonance server from getting a Cometd connection when the device is already connected elsewhere.

Four code paths transition the state to `'connected'`: (1) `notify_playerConnected()` fires when the current player connects to any server, (2) `notify_serverConnected()` fires when the current player's server reconnects, (3) probe timeout expiry when the player is already connected, and (4) the `connectPlayer()` service call when a connected player exists. The transition back to `'searching'` happens via `notify_playerDisconnected()` or `notify_serverDisconnected()`.

The `_setState()` function manages all transitions. Entering `'searching'` restarts the timer at **10-second intervals** and calls `_connect()`. Entering `'connected'` switches to **60-second polling** and calls `_idleDisconnect()` to drop non-essential server connections. The timer drives `_discovery()`, which sends UDP broadcasts on port 3483 and UDAP broadcasts, then adjusts its own interval based on current state.

**The race condition is real but asymmetric.** In the original Logitech firmware (LMS-Community branch), every `_discovery()` tick includes this active code:

```lua
if System:getUUID() then
    squeezenetwork = SlimServer(jnt, "mysqueezebox.com", "mysqueezebox.com")
    self:_serverUpdateAddress(squeezenetwork, jnt:getSNHostname(), 9000, "mysqueezebox.com")
end
```

When state is `'searching'`, this triggers `squeezenetwork:connect()` on every discovery tick. If the SqueezeNetwork player connection completes and fires `notify_playerConnected` before the next discovery tick processes a local server response, state becomes `'connected'` and all subsequent `_serverUpdateAddress` calls for local servers are suppressed. In practice, LAN UDP responses (~1–10ms) typically arrive faster than internet SN connections (~100–500ms), so the first discovery tick usually connects the local server. The danger emerges on **subsequent ticks** or when the Meta layer pre-restores an SN connection from saved settings at startup.

In both the ralph-irving/squeezeplay and triode-jivelite repositories, the SqueezeNetwork code is **commented out** (marked "deprecated"), eliminating this race condition entirely. This is the **only meaningful difference** between the three source files — the state machine, `_serverUpdateAddress`, and all notification handlers are identical.

A subtle Lua operator precedence issue exists in the probe timeout check: `self.state == 'probing_player' or self.state == 'probing_server' and Framework:getTicks() > self.probeUntil`. Because `and` binds tighter than `or`, the `probing_player` state always triggers the timeout check regardless of `probeUntil`, while `probing_server` correctly respects the timer. This appears to be a long-standing quirk rather than an intentional design choice.

---

## The setup wizard blocks local connections until mysqueezebox.com responds

On original Logitech firmware, the SetupWelcome applet runs **before the home menu appears** via its Meta initialization code. The wizard enforces a mandatory sequential flow: language selection → network configuration → SqueezeNetwork registration (display PIN for account linking) → music source selection → `_setupDone()`. The critical insight is that **`_setupDone()` must execute for the device to ever reach the home menu** where normal SlimDiscovery operates.

The SqueezeNetwork registration step attempts to connect to device-specific hostnames:
- `baby.squeezenetwork.com` for Radio
- `fab4.squeezenetwork.com` for Touch  
- `jive.squeezenetwork.com` for Controller

Since Logitech shut down mysqueezebox.com in **February 2024**, factory-reset devices running original firmware **get permanently stuck** in the setup wizard. The networking applet contained Lua `assert` statements that assumed SN availability. When SN is unreachable, these asserts throw exceptions that `AppletManager` catches — but `_setupDone()` never executes, leaving the device trapped. Community reports confirm this is widespread: "After inputting my wifi network password, the radio tries to find 'mysqueezebox.com' and of course fails. I am unable to find out how to input my LMS server."

**Already-configured devices** that completed setup before the shutdown generally continue working with local LMS, but still generate constant failed DNS requests to the SN hostnames in the background. The setup wizard only runs after factory reset or first boot.

A partial workaround exists: **long-pressing the Back button** on the Radio can sometimes escape the wizard to access Settings → Advanced → Networking → Remote Library → Add New Library. This works inconsistently and depends on timing relative to the connection failure.

The community firmware (ralph-irving, 8.5+) systematically removed all SN dependencies: the mandatory registration step was deleted from SetupWelcome, SN hostnames were redirected to localhost, the forced SN connection in SlimDiscovery was commented out, and the SqueezeNetwork PIN applet was removed. **For a Resonance reimplementation targeting original-firmware devices, the most effective approach is either requiring community firmware or implementing DNS redirection** so the device-specific SN hostnames resolve to the Resonance server, allowing the setup wizard to complete.

---

## Hardware SqueezePlay layers gating on top of shared discovery code

The core `SlimDiscoveryApplet.lua` is **identical across all platforms** — Radio, Touch, Boom, and JiveLite all share the same TLV parsing, UDP broadcast mechanism, and state machine. The differences that affect connection behavior are layered on top through platform-specific applets and checks.

**Hardware devices have four gating layers that JiveLite lacks entirely:**

- **SetupWelcome gate**: Hardware runs a platform-specific SetupWelcome applet (baby, fab4, boom variants) that must complete before normal operation. JiveLite has no setup wizard and goes straight to discovery.
- **SqueezeNetwork integration**: Pre-8.5 firmware checks `System:getUUID()` and forces SN connection attempts. JiveLite returns nil/false for this check, bypassing SN entirely.
- **Version comparison bug**: The Radio firmware (7.7.3) has a broken version string comparison that fails to recognize LMS 8.0.0 as newer than 7.7.3. LMS works around this server-side by returning a fake version `7.999.999` (defined as `RADIO_COMPATIBLE_VERSION`) when it detects the `SqueezePlay-baby` user-agent. A "Version Comparison Fix" patch exists via the Applet Installer. Touch and Boom had variants of this bug in 7.x firmware.
- **BSP and networking modules**: Hardware uses native C modules (`baby_bsp`, `squeezeos_bsp`) and `SetupNetworkingApplet` that interact with `/etc/network/config`. These can generate assertion failures that propagate upward and block the setup flow.

The Touch (fab4) uniquely supports **TinySC** (a built-in SqueezeCenter), which affects error handling — network errors are suppressed when TinySC is running. The `ChooseMusicSource` applet manages the poll list of server addresses to probe and is shared across all platforms, making it the primary extension point for adding explicit server addresses beyond broadcast discovery.

For a Resonance reimplementation, **JiveLite provides the cleanest reference implementation**: no SN dependency, no setup wizard gating, pure UDP broadcast → TLV parse → Cometd connect. Community firmware 8.5 aligns hardware behavior much closer to JiveLite by removing the SN references.

| Feature | Hardware (original) | Hardware (community 8.5) | JiveLite |
|---|---|---|---|
| SetupWelcome gate | Yes, mandatory | Yes, SN step removed | None |
| SqueezeNetwork forced | Yes | No (commented out) | No |
| Version comparison bug | Yes (Radio 7.7.3) | Fixed | Not present |
| `System:getUUID()` check | Active | Active | Returns nil |
| SlimDiscovery core | Shared code | Shared code | Same shared code |

---

## Port 17784 is UDAP, not Cometd — and blocking it is harmless

**UDP port 17784 is the UDAP (Universal Discovery and Access Protocol) port**, defined as hex `0x4578` in the Net::UDAP Perl module: `use constant PORT_UDAP => 0x4578`. UDAP is a proprietary broadcast-based protocol originally from SlimDevices for device discovery and initial configuration. It is **completely separate** from both Slimproto discovery (port 3483) and Cometd (TCP port 9000).

SqueezePlay binds port 17784 via the `Udap` module in `SlimDiscoveryApplet` and `SetupSqueezeboxApplet`. The `_discovery()` function sends both a Slimproto discovery broadcast on port 3483 and a UDAP broadcast on port 17784 during each tick. Network captures show the dual broadcast pattern clearly:

```
192.168.32.130.17784 > 255.255.255.255.17784: udp 27    # UDAP discovery
192.168.32.130.49127 > 255.255.255.255.3483: udp 37     # Slimproto discovery
```

UDAP serves four specific functions: device discovery (`adv_discover` messages), initial network configuration (IP, gateway, DNS, WiFi credentials), server assignment (telling a Squeezebox which LMS to connect to), and device status reporting (states like `init`, `wait_slimserver`). It supports ip3k-generation hardware (Squeezebox 3/Classic, Boom, Receiver/Duet, Transporter) and SqueezePlay software. Touch and Radio use UDAP for some discovery but not full configuration.

**Blocking port 17784 will NOT affect Cometd connections.** Cometd operates over HTTP on TCP port 9000, and server discovery works independently via port 3483 Slimproto broadcasts. The UDAP traffic on 17784 is only relevant for discovering and configuring unconfigured Squeezebox hardware on the local network — a function typically handled by the Controller (Duet) or `Net::UDAP` command-line tools. A Resonance server does not need to listen on or respond to port 17784 unless it wants to replicate the Controller's ability to set up unconfigured hardware.

| Port | Protocol | Purpose | Needed for Resonance? |
|---|---|---|---|
| 3483 | UDP broadcast + TCP | Slimproto: server discovery (UDP) and player control (TCP) | **Yes** — discovery |
| 9000 | TCP (HTTP) | Web interface, Cometd, streaming | **Yes** — Cometd |
| 9090 | TCP | CLI (Command Line Interface) | Optional |
| 17784 | UDP broadcast | UDAP: device setup/configuration | **No** — unless configuring hardware |

---

## Conclusion: what this means for Resonance

The four findings connect into a coherent picture of why a Resonance server might not receive Cometd connections despite correctly responding to discovery broadcasts. The **`_serverUpdateAddress()` state gate** is the immediate cause: if the device is in `'connected'` state (attached to any server, including a stale SN connection), your server's discovery response updates its address but never triggers `connect()`. The **setup wizard** is the likely upstream cause on factory-reset hardware running original firmware — the device never reaches normal discovery because it's stuck trying to contact the defunct mysqueezebox.com. The **version comparison bug** on Radio adds another failure mode where the device rejects the server after successful discovery. And **port 17784 UDAP traffic** is a red herring that does not affect Cometd.

Three practical paths forward emerge. First, target devices running **community firmware 8.5+** or JiveLite, which eliminate the SN dependency and setup wizard blocking. Second, for original-firmware devices, implement **DNS redirection** so `baby.squeezenetwork.com` / `fab4.squeezenetwork.com` resolve to the Resonance server, allowing the setup wizard to complete. Third, ensure the Resonance server returns a **compatible version string** (e.g., `7.999.999` for Radio user-agents) to avoid the version comparison rejection. The core discovery-to-Cometd flow is clean and well-defined once these surrounding barriers are removed.