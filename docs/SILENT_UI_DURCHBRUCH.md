# 🎉 Silent UI — Durchbruch & Neue Blocker

> **UUID-Reset beweist State-Gate-Hypothese. Drei neue Bugs gefunden.**
> Session: 2026-02-06 (ws23.pcapng)

---

## 1. Durchbruch: HTTP-Trigger gelöst ✅

Durch **Löschen von `cache/server_uuid`** wurde das „State Gate" im Squeezebox Radio durchbrochen.

```
VORHER (ws21):                        NACHHER (ws23):
Discovery ✅                          Discovery ✅
Slimproto ✅                          Slimproto ✅
HTTP/Cometd ❌ ← BLOCKIERT            HTTP/Cometd ✅ ← DURCHBRUCH!
```

**Beweis:** `ws23.pcapng` enthält `POST /cometd` — das Radio macht jetzt den HTTP-Handshake.

**Root Cause bestätigt:**
- Das Gerät hatte die alte UUID im Cache
- Bei bekannter UUID → `_serverUpdateAddress()` → kein `connect()`
- Bei neuer UUID → `newServer()` → `connect()` → **HTTP!**

### Implikation für den Produktivbetrieb

Die UUID **muss** persistent bleiben (sonst verlieren alle Clients ihre Verbindung bei jedem Server-Restart). Das State-Gate-Problem tritt nur beim **ersten Kontakt** auf, wenn das Gerät eine alte/fehlgeschlagene Verbindung gecacht hat.

**Langfristige Lösung:** Nicht UUID rotieren, sondern sicherstellen, dass der Server beim ersten Kontakt korrekt antwortet, damit das Gerät nicht in einem kaputten `connected`-State hängen bleibt.

---

## 2. VERS-Widerspruch: Aufgelöst

Der Code sendet `7.999.999` (nicht `7.9.1` wie in AI_BOOTSTRAP.md dokumentiert).

| Quelle | VERS-Wert |
|--------|-----------|
| `resonance/server.py` Zeile 181 | `"7.999.999"` |
| `resonance/protocol/discovery.py` Default | `"7.999.999"` |
| AI_BOOTSTRAP.md (Doku) | `"7.9.1"` ← **FALSCH** |
| ws23.pcapng (Realität) | `"7.999.999"` (vermutlich) |

**Fazit:** AI_BOOTSTRAP.md muss korrigiert werden. `7.999.999` funktioniert offenbar — das Radio hat den Handshake gemacht.

**TODO:** AI_BOOTSTRAP.md aktualisieren:
- Alle Stellen wo `"7.9.1"` steht → `"7.999.999"` korrigieren
- Decision Log updaten

---

## 3. Neue Blocker (Menü wird nicht angezeigt)

HTTP fließt, aber das Gerät zeigt **kein Menü**. Drei Bugs gefunden:

### Bug A: Die „127.0.0.1"-Falle 🔴 KRITISCH

**Symptom:** `serverstatus` Event enthält `"ip": "127.0.0.1"`.

```json
{
  "ip": "127.0.0.1",
  "httpport": "9000",
  "version": "...",
  "player count": 0
}
```

**Problem:** Das Radio nutzt diese IP, um weitere Ressourcen zu laden (Icons, Cover Art, Menüdaten). `127.0.0.1` zeigt auf das Radio selbst → alle Folge-Requests scheitern.

**Fix benötigt in:** `resonance/web/handlers/status.py`

```python
# FALSCH:
"ip": "127.0.0.1"

# RICHTIG:
"ip": server_lan_ip  # z.B. "192.168.1.30"
```

**Woher die LAN-IP nehmen?**
- Option 1: Aus der Discovery-Logik (`_get_local_ip_for_client()`)
- Option 2: Aus der Slimproto-Verbindung (`get_advertise_ip_for_player()`)
- Option 3: Aus der HTTP-Request Source (`request.client.host` → Reverse-Lookup)

### Bug B: „Missing Player" — `player count: 0` 🔴 KRITISCH

**Symptom:** `serverstatus` meldet keine Player.

```json
{
  "player count": 0,
  "players_loop": []
}
```

**Problem:** Das Radio sucht sich selbst in der `players_loop`. Wenn es sich nicht findet, glaubt es, nicht für diesen Server registriert zu sein → kein Menü.

**Root Cause:** Hängt vermutlich mit Bug C zusammen — der Player wird registriert, dann bricht die TCP-Verbindung ab, der Player wird deregistriert, und wenn der `serverstatus` kommt, ist die Registry leer.

**Reihenfolge:**
```
1. HELO → Player registriert ✅
2. TCP-Fehler (WinError 121) → Player deregistriert ❌
3. serverstatus-Request → player count: 0 ❌
4. Radio: "Ich bin kein Player hier" → kein Menü ❌
```

### Bug C: Slimproto TCP-Instabilität (`WinError 121`) 🔴 KRITISCH

**Symptom:** Kurz nach Verbindungsaufbau:

```
OSError: [WinError 121] Das Zeitlimit für die Semaphore wurde erreicht
```

**Was das ist:** Windows-spezifischer TCP-Timeout. Der Slimproto-Socket wird von Windows geschlossen, weil eine Operation zu lange dauert.

**Mögliche Ursachen:**

| Ursache | Wahrscheinlichkeit |
|---------|-------------------|
| TCP Keepalive nicht konfiguriert → Windows schließt idle Connection | 🔴 Hoch |
| Blocking I/O im async Context → Event-Loop blockiert | 🟡 Möglich |
| Firewall/Antivirus interferiert mit TCP 3483 | 🟡 Möglich |
| Windows Semaphore-Limit bei vielen gleichzeitigen Connections | 🟢 Unwahrscheinlich |

**Fix-Ansätze:**

```python
# TCP Keepalive aktivieren (in slimproto.py, nach accept):
import socket
client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

# Windows-spezifisch: Keepalive-Intervall setzen
if hasattr(socket, 'SIO_KEEPALIVE_VALS'):
    # Keepalive nach 10s, Intervall 5s, 3 Retries
    client_socket.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 5000))
```

---

## 4. Abhängigkeitskette der Bugs

```
Bug C (TCP-Crash)
  └── verursacht Bug B (Player deregistriert → count: 0)
        └── verursacht: Kein Menü (Radio findet sich nicht)

Bug A (127.0.0.1)
  └── verursacht: Keine Icons/Cover/Folge-Requests
        └── verursacht: Selbst MIT Menü wäre es kaputt
```

**Fix-Reihenfolge:**
1. **Bug C zuerst** — TCP stabilisieren (WinError 121)
2. **Bug B löst sich** — Wenn TCP stabil → Player bleibt registriert
3. **Bug A parallel** — LAN-IP statt 127.0.0.1 ist unabhängig

---

## 5. Aktionsplan

### Sofort (diese Session)

| # | Aufgabe | Datei | Aufwand |
|---|---------|-------|---------|
| 1 | **TCP Keepalive** für Slimproto-Sockets aktivieren | `protocol/slimproto.py` | 15 Min |
| 2 | **LAN-IP** statt `127.0.0.1` im serverstatus | `web/handlers/status.py` | 10 Min |
| 3 | **VERS-Doku** korrigieren (7.999.999, nicht 7.9.1) | `docs/AI_BOOTSTRAP.md` | 5 Min |

### Danach (Verifikation)

| # | Aufgabe |
|---|---------|
| 4 | Server neu starten, Log prüfen (Startup-Log mit UUID/VERS) |
| 5 | UUID **NICHT** löschen (wir wollen den stabilen Zustand testen) |
| 6 | Radio rebooten + Wireshark → ws24.pcapng |
| 7 | Prüfen: `player count > 0`? Menü sichtbar? |

---

## 6. Decision Log Update

| Entscheidung | Begründung |
|-------------|------------|
| **UUID-Reset = State-Gate-Fix** | ws23 beweist: Neue UUID → `connect()` → HTTP ✅ |
| **UUID muss persistent bleiben** | Rotation bei jedem Start würde alle Clients disconnecten |
| **VERS = `7.999.999` ist korrekt** | Radio akzeptiert es (ws23 beweist es). Doku war falsch. |
| **Bug C (TCP) hat höchste Prio** | Verursacht Bug B kaskadierend |
| **LAN-IP parallel fixen** | Unabhängig von TCP, aber genauso kritisch für Funktionalität |

---

## 7. Zusammenfassung

```
┌─────────────────────────────────────────────────────────┐
│  DURCHBRUCH ✅                                          │
│  UUID-Reset → HTTP fließt → Hypothese bestätigt         │
│                                                         │
│  NEUE BLOCKER ❌                                        │
│  A: 127.0.0.1 statt LAN-IP im serverstatus             │
│  B: player count: 0 (Radio findet sich nicht)           │
│  C: WinError 121 crasht Slimproto TCP                   │
│                                                         │
│  FIX-KETTE                                              │
│  C (TCP Keepalive) → B (löst sich) → A (LAN-IP)        │
│                                                         │
│  NÄCHSTER SCHRITT                                       │
│  TCP Keepalive in slimproto.py einbauen                 │
│  LAN-IP in status.py einbauen                           │
│  Test: ws24.pcapng                                      │
└─────────────────────────────────────────────────────────┘
```

> **Der Durchbruch ist real.** HTTP fließt zum ersten Mal.
> Drei Bugs stehen zwischen uns und dem funktionierenden Menü.
> Alle drei sind **Server-seitig fixbar** — kein Infrastruktur-Hack nötig.