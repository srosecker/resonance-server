# 🔇 The Silent UI — Analyse & Lösungsplan

> **Warum Squeezebox-Hardware Resonance „hört", aber nicht „sieht"**
> Session: 2026-02-06

---

## 1. Faktenlage (ws21.pcapng)

| Prüfpunkt | Ergebnis |
|-----------|----------|
| **Discovery TLVs** | ✅ `VERS=7.9.1`, `JSON=9000`, `UUID=36 Zeichen` — alles korrekt |
| **Slimproto TCP (3483)** | ✅ HELO, strm, stat — Verbindung steht |
| **HTTP/Cometd (9000)** | ❌ Kein einziger `POST /cometd` |
| **MySB/SN DNS-Queries** | ❌ Kein `squeezenetwork` oder `mysqueezebox` im Klartext |
| **Squeezelite** | ✅ Funktioniert perfekt (hat kein UI → kein Problem) |

```
Gerät-Verhalten:
  Audio-Ebene (Slimproto):  ████████████████████ ✅ Verbunden
  UI-Ebene (HTTP/Cometd):   ░░░░░░░░░░░░░░░░░░░ ❌ Totenstille
```

---

## 2. Root Cause: Das „State Gate"

### Die Zustandsmaschine im Client

SqueezePlay (die Software auf Boom/Radio/Touch) hat eine interne Zustandsmaschine. Die entscheidende Funktion in `SlimDiscoveryApplet.lua`:

```lua
function onServerDiscovered(uuid, name, ip, port)
    if not servers[uuid] then
        -- NEUER Server! → Objekt anlegen → connect() aufrufen
        servers[uuid] = newServer(uuid, name, ip, port)
        server:connect()  -- ← TRIGGERT HTTP/COMETD!
    else
        -- BEKANNTER Server → nur Adresse updaten
        _serverUpdateAddress(servers[uuid], ip, port)
        -- KEIN connect()! State bleibt wie er ist!
    end
end
```

Und in `_serverUpdateAddress`:

```lua
function _serverUpdateAddress(server, ip, port)
    server:updateAddress(ip, port)

    -- DER BLOCKER:
    if state == 'searching' or state == 'probing' then
        server:connect()  -- HTTP/Cometd wird initiiert
    end
    -- Wenn state == 'connected' → NICHTS passiert.
end
```

### Was das bedeutet

```
┌──────────┐    ┌──────────┐    ┌──────────────┐
│ searching │───►│ probing  │───►│  connected   │ ◄── 🔒
└──────────┘    └──────────┘    └──────────────┘
     │               │                │
     ▼               ▼                ▼
 connect() ✅    connect() ✅     BLOCKIERT ❌
```

Das Gerät glaubt, es sei bereits **`connected`** — entweder zu einer alten Resonance-Instanz (mit gleicher UUID) oder zu einem Phantom-Server.

---

## 3. Die UUID-Hypothese

### Das Problem

Resonance verwendet eine **persistente UUID** in `cache/server_uuid`:

```python
# resonance/server.py — get_or_create_server_uuid()
SERVER_UUID_FILE = Path("cache/server_uuid")

if SERVER_UUID_FILE.exists():
    stored_uuid = SERVER_UUID_FILE.read_text().strip()
    if len(stored_uuid) == 36 and stored_uuid.count('-') == 4:
        return stored_uuid  # ← Gleiche UUID wie letzte Session
```

**Szenario:**
1. Gerät bootet, empfängt Discovery mit UUID `abc-123-...`
2. Gerät: `servers["abc-123-..."]` existiert schon (von letztem Versuch)
3. → `_serverUpdateAddress()` statt `newServer()` + `connect()`
4. State ist `connected` (oder `disconnected` mit gecachtem Server)
5. → **Kein HTTP-Connect!**

### Die Lösung

Neue UUID → Gerät sagt `servers[uuid] == nil` → `newServer()` → `connect()` → **HTTP!**

```
Alte UUID bekannt:     Discovery → updateAddress() → 🔇 Stille
Neue UUID unbekannt:   Discovery → newServer() → connect() → 🔊 HTTP!
```

---

## 4. Aktionsplan

### Option 1: UUID löschen (30 Sekunden) 🔴 SOFORT TESTEN

```powershell
# 1. Server stoppen (Ctrl+C)

# 2. UUID löschen
# (Pfad kann variieren, meist im Projekt-Root unter 'cache/')
del resonance-server\cache\server_uuid

# 3. Server starten (neue UUID wird automatisch generiert)
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --verbose

# 4. Gerät rebooten (Strom weg, 5 Sekunden warten, Strom dran)

# 5. Wireshark auf Port 9000 filtern
#    → Kommt jetzt "POST /cometd"?
```

### Option 2: Sequenz-Trick (falls Option 1 nicht reicht)

```powershell
# 1. Server stoppen
# 2. UUID löschen: del resonance-server\cache\server_uuid
# 3. Gerät rebooten (Strom weg, 10 Sekunden warten)
# 4. WARTEN bis Gerät "Searching" anzeigt oder 30 Sekunden vergehen
# 5. DANN erst Server starten
```

**Idee:** Gerät bootet ohne Server → geht in State `searching` → entdeckt dann neuen Server → `connect()`.

### Option 3: "Bibliothek umschalten" am Gerät

Falls Menü sichtbar: `Einstellungen → Erweitert → Netzwerk → Bibliothek umschalten`

> ⚠️ Unwahrscheinlich, da ohne HTTP kein Menü angezeigt wird (Henne-Ei-Problem).

### Option 4: DNS-Spoofing (falls alles andere fehlschlägt)

```
# Pi-Hole / Router DNS:
mysqueezebox.com          → 192.168.1.x  (Resonance IP)
api.mysqueezebox.com      → 192.168.1.x
baby.squeezenetwork.com   → 192.168.1.x
fab4.squeezenetwork.com   → 192.168.1.x
```

> Auch wenn ws21 keine MySB-DNS-Queries zeigte: DNS-Cache oder zu kurzer Capture könnten das maskiert haben.

### Option 5: Community-Firmware (sauberste Langzeitlösung)

Für **Squeezebox Radio**: [Community Firmware](https://forums.slimdevices.com/forum/user-forums/logitech-media-server/842340-community-squeezebox-radio-firmware-builds) von Michael Herger.
- Entfernt MySqueezebox-Abhängigkeit
- Bootet direkt ins LMS-Menü

Für **Boom/Touch**: Noch keine Community-Firmware verfügbar → DNS-Spoofing als Fallback.

---

## 5. Verifikation

### Erfolgs-Kriterium

Nach dem Test neues Capture `ws22.pcapng` erstellen. **Erfolg** = mindestens einer dieser Einträge:

```powershell
# Im Wireshark-Capture nach HTTP suchen:
tshark -r tests/ws22.pcapng -Y "http.request.method == POST and http.request.uri contains cometd"
```

### Erwarteter Flow bei Erfolg

```
1. Discovery: UUID (NEU) → Gerät: "Unbekannter Server!"
2. Gerät: newServer() → connect()
3. POST /cometd: /meta/handshake ← DAS wollen wir sehen!
4. POST /cometd: /meta/connect (streaming)
5. POST /cometd: /slim/subscribe (serverstatus)
6. POST /cometd: /slim/request (menu)
7. Display zeigt Menü 🎉
```

---

## 6. Warum NICHT Slimproto verzögern?

Die Idee, Slimproto künstlich zu verzögern, ist **falsch** weil:

1. **Slimproto und HTTP sind unabhängig** — Discovery triggert beide parallel (Research_gold)
2. **Squeezelite würde brechen** — braucht schnellen Slimproto-Handshake
3. **Das Problem ist State-Persistenz**, nicht Timing

---

## 7. Decision Log Update

| Entscheidung | Begründung |
|-------------|------------|
| **UUID-Reset als erster Test** | Gerät cached Server-Objekte nach UUID; neue UUID erzwingt `connect()` |
| **Kein Slimproto-Delay** | Slimproto/HTTP sind unabhängig, würde Squeezelite brechen |
| **DNS-Spoofing als Backup** | Falls UUID-Reset nicht reicht, MySB-Redirect als nächster Schritt |
| **Server-Code ist korrekt** | Discovery, Cometd, Streaming — alles verifiziert. Problem ist Client-State |

---

## 8. Zusammenfassung

```
┌─────────────────────────────────────────────────────────┐
│  DIAGNOSE                                               │
│                                                         │
│  Gerät hat UUID im Cache → kennt "diesen" Server        │
│  → _serverUpdateAddress() statt server:connect()        │
│  → HTTP/Cometd wird NICHT getriggert                    │
│                                                         │
│  THERAPIE                                               │
│                                                         │
│  del resonance-server\cache\server_uuid → Neue UUID     │
│  → Gerät: "Neuer Server!" → connect()                   │
│  → HTTP/Cometd → Menüs → 🎉                            │
│                                                         │
│  BEWEIS                                                 │
│                                                         │
│  ws22.pcapng nach UUID-Reset                            │
│  Erfolg = "POST /cometd" im Capture                     │
└─────────────────────────────────────────────────────────┘
```
