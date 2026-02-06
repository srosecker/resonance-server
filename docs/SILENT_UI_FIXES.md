# 🔧 Silent UI — Fixes für die drei Blocker

> **Bug C (TCP), Bug A (127.0.0.1), Bug B (player count: 0)**
> Session: 2026-02-06

---

## Bug A: Die „127.0.0.1"-Falle — Root Cause gefunden ✅

### Wo das Problem entsteht

Die Ursache ist **nicht** in `status.py`, sondern in `CommandContext.__post_init__()`:

```python
# resonance/web/handlers/__init__.py, Zeile 69-71
def __post_init__(self) -> None:
    if self.server_host == "0.0.0.0":
        self.server_host = "127.0.0.1"  # ← DAS IST DAS PROBLEM
```

Wenn der Server auf `0.0.0.0` gebunden ist (Standard), wird `server_host` **pauschal** auf `127.0.0.1` gesetzt. Das wird dann in `cmd_serverstatus()` als `"ip"` gemeldet:

```python
# resonance/web/handlers/status.py, Zeile 76
"ip": ctx.server_host,  # ← "127.0.0.1" vom __post_init__
```

Und in allen Cover-URLs:

```python
# status.py, Zeile 287
server_url = f"http://{ctx.server_host}:{ctx.server_port}"
# → "http://127.0.0.1:9000" ← Radio kann das nicht erreichen!
```

### Fix

Der `CommandContext` braucht die **echte LAN-IP** des Servers, nicht einen pauschalen Fallback. Die beste Quelle ist die selbe Logik, die `SlimprotoServer.get_advertise_ip_for_player()` schon nutzt — einen UDP-Socket zum Client öffnen und die lokale IP ermitteln.

**Option 1: Pro-Request IP-Auflösung (sauber, aber aufwändiger)**

Den `CommandContext` um eine Methode erweitern, die die Client-IP nutzt, um die richtige Server-IP zu ermitteln. Das erfordert, dass die Client-IP beim Context-Aufbau bekannt ist.

**Option 2: Einmalig beim Serverstart (einfach, reicht für Heimnetz)**

Beim Serverstart die LAN-IP ermitteln und im Context durchreichen. Das reicht für das typische Single-Subnet-Heimnetz.

### Empfohlener Fix (Option 2)

**Datei: `resonance/web/handlers/__init__.py`**

```python
import socket

@dataclass
class CommandContext:
    # ... bestehende Felder ...
    server_host: str = "127.0.0.1"

    def __post_init__(self) -> None:
        if self.server_host == "0.0.0.0":
            # Ermittle die tatsächliche LAN-IP statt pauschal 127.0.0.1
            self.server_host = self._detect_lan_ip()

    @staticmethod
    def _detect_lan_ip() -> str:
        """Detect the primary LAN IP address of this machine."""
        try:
            # Verbinde zu einem öffentlichen DNS (kein Paket wird gesendet)
            # um die lokale Interface-IP zu ermitteln
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
```

> **Achtung:** `8.8.8.8` ist nur ein Routing-Ziel — es wird kein Paket gesendet. Der Trick funktioniert auch offline, solange ein Default-Gateway existiert. Alternativ könnte man die IP des anfragenden Clients verwenden (wie Discovery es tut), aber das erfordert den Client-Context bei der CommandContext-Erstellung.

---

## Bug C: TCP-Instabilität (`WinError 121`) — Fix

### Was passiert

`WinError 121` = "Das Zeitlimit für die Semaphore wurde erreicht" — ein Windows-spezifischer TCP-Timeout. Der Socket wird geschlossen, weil keine Daten fließen und kein Keepalive konfiguriert ist.

### Wo der Fix hin muss

In `slimproto.py`, Methode `_handle_connection()`, direkt nach dem Akzeptieren der Verbindung — **bevor** der HELO gelesen wird.

**Datei: `resonance/protocol/slimproto.py`**

Die `start()`-Methode nutzt `asyncio.start_server()`, das den `writer` mit dem Socket erstellt. Der Socket ist über `writer.get_extra_info('socket')` erreichbar.

```python
async def _handle_connection(
    self,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    peername = writer.get_extra_info("peername")
    remote_addr = f"{peername[0]}:{peername[1]}" if peername else "unknown"

    logger.info("New connection from %s", remote_addr)

    # === NEU: TCP Keepalive aktivieren ===
    sock = writer.get_extra_info("socket")
    if sock is not None:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Windows-spezifisch: Keepalive-Parameter setzen
            # (onoff=1, keepalive_time=10000ms, keepalive_interval=5000ms)
            if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                sock.ioctl(
                    socket.SIO_KEEPALIVE_VALS,
                    (1, 10000, 5000),
                )
            logger.debug("TCP keepalive enabled for %s", remote_addr)
        except Exception as e:
            logger.debug("Could not set TCP keepalive for %s: %s", remote_addr, e)
    # === ENDE NEU ===

    client = PlayerClient(reader, writer)
    # ... Rest wie bisher ...
```

### Zusätzlich: OSError abfangen in `_message_loop`

Der `WinError 121` ist ein `OSError`, der aktuell nicht abgefangen wird und den ganzen Connection-Handler crasht:

```python
async def _message_loop(self, client, reader) -> None:
    while self._running and client.is_connected:
        try:
            command, payload = await self._read_message(reader)
        except asyncio.IncompleteReadError:
            logger.debug("Client %s disconnected (incomplete read)", client.id)
            break
        except ConnectionResetError:
            logger.debug("Client %s connection reset", client.id)
            break
        # === NEU: OSError abfangen (WinError 121 etc.) ===
        except OSError as e:
            logger.warning("Client %s socket error: %s", client.id, e)
            break
        # === ENDE NEU ===

        client.update_last_seen()
        # ... Rest wie bisher ...
```

---

## Bug B: `player count: 0` — Löst sich durch Bug C

Wenn die TCP-Verbindung nicht mehr crasht (Bug C Fix), bleibt der Player registriert. Dann ist `player count > 0` im nächsten `serverstatus`.

**Kein separater Fix nötig** — Bug B ist ein Symptom von Bug C.

### Verifikation

Nach den Fixes prüfen:
1. Server starten
2. Radio verbinden lassen (UUID ist jetzt bekannt → sollte bei Reboot reconnecten)
3. Im Log prüfen: Kein `WinError 121`?
4. In ws24.pcapng prüfen: `"player count": 1`?

---

## Zusammenfassung aller Änderungen

### Datei 1: `resonance/web/handlers/__init__.py`

| Zeile | Änderung |
|-------|----------|
| 1 | `import socket` hinzufügen |
| 69-71 | `__post_init__()` → LAN-IP Erkennung statt `"127.0.0.1"` |
| NEU | `_detect_lan_ip()` Hilfsmethode |

### Datei 2: `resonance/protocol/slimproto.py`

| Zeile | Änderung |
|-------|----------|
| ~388 | TCP Keepalive nach Connection-Accept (in `_handle_connection`) |
| ~637-642 | `OSError` im `except`-Block von `_message_loop` abfangen |

### Nicht geändert

- `resonance/web/handlers/status.py` — Braucht keinen Fix, weil das Problem in `CommandContext` liegt
- `resonance/server.py` — UUID/VERS bleiben wie sie sind

---

## Test-Reihenfolge

```
1. Fixes einbauen (zwei Dateien)
2. Tests laufen lassen: pytest -v (alle 356 müssen grün bleiben)
3. Server starten (UUID NICHT löschen — wir testen den stabilen Zustand)
4. Radio rebooten
5. Wireshark: ws24.pcapng
6. Prüfen:
   - [ ] Kein WinError 121 im Log?
   - [ ] player count > 0 im serverstatus?
   - [ ] IP ist LAN-IP (nicht 127.0.0.1)?
   - [ ] Radio zeigt Menü?
```

---

## Decision Log

| Entscheidung | Begründung |
|-------------|------------|
| **LAN-IP via UDP-Socket-Trick** | Gleiche Methode wie Discovery, kein Netzwerk-Traffic, funktioniert offline |
| **TCP Keepalive 10s/5s** | Aggressiv genug um Windows-Timeout zu verhindern, nicht zu aggressiv für WLAN |
| **OSError abfangen** | WinError 121 ist ein OSError, nicht ConnectionResetError |
| **Bug B kein eigener Fix** | Ist Symptom von Bug C (TCP-Crash → Player deregistriert) |
| **`8.8.8.8` als Routing-Ziel** | Standard-Trick, kein Paket gesendet, funktioniert auf allen Plattformen |