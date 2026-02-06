# Squeezebox Boom Cometd Findings

> **Session: 2026-02-05 / 2026-02-06** - Wireshark-basierte Analyse der Boom-Verbindung

## Übersicht

Die Squeezebox Boom verwendet ein eingebettetes SqueezePlay/Jive UI, das über Cometd/Bayeux mit dem Server kommuniziert. Diese Dokumentation beschreibt die gefundenen Unterschiede zwischen unserer Implementierung und LMS.

## Protokoll-Flow

```
┌──────────────┐                              ┌──────────────┐
│  Boom (Jive) │                              │   Resonance  │
└──────────────┘                              └──────────────┘
       │                                              │
       │  1. UDP Discovery (Port 3483)                │
       │ ─────────────────────────────────────────────►
       │  ◄──────── TLVs: IPAD, NAME, JSON, UUID ─────│
       │                                              │
       │  2. Slimproto TCP (Port 3483)                │
       │ ─────────────────────────────────────────────►
       │  ◄──────────── HELO/vers/setd ───────────────│
       │                                              │
       │  3. HTTP/Cometd (Port 9000) - Connection A   │
       │ ───── POST /cometd: /meta/handshake ─────────►
       │  ◄──────── clientId: "7a6364c4" ─────────────│
       │                                              │
       │ ───── POST /cometd: /meta/connect ───────────►  (Streaming!)
       │       + /meta/subscribe: /7a6364c4/**        │
       │  ◄──────── StreamingResponse (chunked) ──────│  (Connection bleibt offen!)
       │                                              │
       │  4. HTTP/Cometd (Port 9000) - Connection B   │
       │ ───── POST /cometd: /slim/subscribe ─────────►  (serverstatus, firmwareupgrade)
       │  ◄──────── successful: true ─────────────────│
       │                                              │
       │  ◄═══════ Daten auf Connection A ════════════│  (Events via Streaming!)
       │          /7a6364c4/slim/serverstatus         │
       │          /7a6364c4/slim/firmwarestatus       │
       │                                              │
       │  5. /slim/request für Menü                   │
       │ ───── POST /cometd: /slim/request ───────────►  (menu 0 100 direct:1)
       │  ◄──────── successful: true ─────────────────│
       │                                              │
       │  ◄═══════ Menü-Daten auf Connection A ═══════│  (Event via Streaming!)
       │          /7a6364c4/slim/request              │
       │                                              │
```

## Gefundene Probleme & Fixes

### 0. UUID-Format falsch (ws15.pcapng) - KRITISCH!

**Problem:** Boom macht Discovery, empfängt TLVs korrekt, macht aber **KEINE TCP-Verbindung** (weder Slimproto noch HTTP).

**Analyse:**
```
# Resonance Response
TLV: IPAD len=12 value="192.168.1.30"
TLV: NAME len=9 value="Resonance"
TLV: JSON len=4 value="9000"
TLV: VERS len=5 value="9.0.0"
TLV: UUID len=8 value="db2d3683"       ← FALSCH!

# LMS Response (aus lms.pcap)
TLV: NAME len=28 value="Lyrion Music Server (Docker)"
TLV: JSON len=4 value="9000"
TLV: VERS len=5 value="9.0.3"
TLV: UUID len=36 value="1a421556-465b-4802-9599-654aa2d6dbd4"  ← RICHTIG!
```

**LMS-Code (slimserver.pl):**
```perl
if ( !$prefs->get('server_uuid') ) {
    $prefs->set( server_uuid => UUID::Tiny::create_UUID_as_string( UUID_V4() ) );
}
```

**Fix:** `resonance/server.py` - `get_or_create_server_uuid()` generiert jetzt vollständiges UUID v4 (36 Zeichen mit Bindestrichen) statt 8 Zeichen.

**Datei:** `resonance/server.py`

### 1. Streaming Connection Type (ws2.pcapng)

**Problem:** Boom sendet `supportedConnectionTypes: ["streaming"]`, wir antworteten mit `["long-polling"]`.

**Fix:** `supportedConnectionTypes: ["streaming", "long-polling"]` in Handshake-Response.

**Datei:** `resonance/web/cometd.py` - `handshake()`

### 2. clientId aus Response-Channel extrahieren (ws2.pcapng, ws3.pcapng)

**Problem:** Bei `/slim/subscribe` sendet Boom **kein** explizites `clientId` im JSON!

```json
// Boom sendet:
{
  "channel": "/slim/subscribe",
  "data": {
    "request": ["", ["serverstatus", 0, 50, "subscribe:60"]],
    "response": "/7a6364c4/slim/serverstatus"  // <-- clientId hier!
  }
}
```

**LMS-Code (Slim/Web/Cometd.pm:187-188):**
```perl
# Pull clientId out of response channel
($clid) = $obj->{data}->{response} =~ m{/([0-9a-f]{8})/};
```

**Fix:** clientId aus Response-Channel extrahieren für `/slim/subscribe`, `/slim/unsubscribe`, `/slim/request`.

**Datei:** `resonance/web/routes/cometd.py` - `_process_message()`

### 3. /slim/subscribe muss Request ausführen (ws3.pcapng)

**Problem:** Wir registrierten nur die Subscription, führten aber den Request nicht aus!

**LMS-Verhalten (Slim/Web/Cometd.pm:414-420):**
```perl
my $result = handleRequest( {
    request  => $request,
    response => $response,
    type     => 'subscribe',
} );
# ...
if ( exists $result->{data} ) {
    $manager->deliver_events( $result );  # Sofort senden!
}
```

**Fix:** Bei `/slim/subscribe`:
1. Request ausführen via JSON-RPC Handler
2. Ergebnis sofort als Event an Client senden
3. Subscription für zukünftige Updates registrieren

**Datei:** `resonance/web/cometd.py` - `slim_subscribe()`

### 4. /slim/request Daten-Extraktion (ws4pcapng.pcapng)

**Problem:** Request-Daten wurden falsch extrahiert.

```python
# Falsch:
data = request.get("data")  # = {"request": [...], "response": "..."}
if isinstance(data, list):  # False! data ist dict!

# Richtig:
data = request.get("data", {})
req_data = data.get("request")  # = [player_id, command]
```

**Datei:** `resonance/web/cometd.py` - `slim_request()`

### 5. /slim/request Ergebnis auf Response-Channel (ws4pcapng.pcapng)

**Problem:** Ergebnis wurde in der HTTP-Response zurückgegeben, nicht auf dem Streaming-Channel.

**LMS-Verhalten (Slim/Web/Cometd.pm:583-589):**
```perl
# If the request was not async, tell the manager to deliver the results
if ( exists $result->{data} ) {
    if ( $transport eq 'long-polling' ) {
        push @{$events}, $result;
    } else {
        $manager->deliver_events( $result );  # Für Streaming!
    }
}
```

**Fix:** Ergebnis als Event auf `response`-Channel an Client senden (für Streaming-Clients).

**Datei:** `resonance/web/cometd.py` - `slim_request()`

### 6. menustatus Command fehlt (ws4pcapng.pcapng)

**Problem:** Boom subscribed für `menustatus`, wir hatten keinen Handler.

**Symptom im Capture:**
```json
{"channel": "/7a6364c4/slim/menustatus/00:04:20:26:84:ae",
 "data": {"error": "Unknown command: menustatus"}}
```

**Fix:** Stub-Handler für `menustatus` implementiert.

**Datei:** `resonance/web/handlers/menu.py` - `cmd_menustatus()`

## Wireshark-Analyse Befehle

```powershell
# HTTP-Pakete anzeigen
"C:\Program Files\Wireshark\tshark.exe" -r tests/ws4pcapng.pcapng -Y "http"

# Hex-Daten extrahieren
"C:\Program Files\Wireshark\tshark.exe" -r tests/ws4pcapng.pcapng -Y "http" -T fields -e frame.number -e http.file_data

# Hex zu JSON dekodieren (Python)
python -c "import json; data='<hex>'; print(json.dumps(json.loads(bytes.fromhex(data).decode()), indent=2))"

# Pakete auf bestimmtem Port
"C:\Program Files\Wireshark\tshark.exe" -r tests/ws4pcapng.pcapng -Y "tcp.port == 53458"
```

## Datenformat-Referenz

### /slim/subscribe Request
```json
{
  "channel": "/slim/subscribe",
  "id": 1,
  "data": {
    "request": ["", ["serverstatus", 0, 50, "subscribe:60"]],
    "response": "/7a6364c4/slim/serverstatus"
  }
}
```

### /slim/subscribe Response (Acknowledgement)
```json
{
  "channel": "/slim/subscribe",
  "successful": true,
  "clientId": "7a6364c4",
  "id": 1
}
```

### Initiale Daten (auf Streaming-Channel)
```json
{
  "channel": "/7a6364c4/slim/serverstatus",
  "id": 1,
  "data": {
    "version": "0.1.0",
    "player count": 1,
    "players_loop": [...]
  }
}
```

### /slim/request Request
```json
{
  "channel": "/slim/request",
  "id": 4,
  "data": {
    "request": ["00:04:20:26:84:ae", ["menu", 0, 100, "direct:1"]],
    "response": "/7a6364c4/slim/request"
  }
}
```

### /slim/request Response (Acknowledgement only!)
```json
{
  "channel": "/slim/request",
  "successful": true,
  "clientId": "7a6364c4",
  "id": 4
}
```

### /slim/request Daten (auf Streaming-Channel)
```json
{
  "channel": "/7a6364c4/slim/request",
  "id": 4,
  "data": {
    "count": 5,
    "item_loop": [...]
  }
}
```

## LMS-Referenzdateien

- `Slim/Web/Cometd.pm` - Cometd-Handler, `/slim/subscribe`, `/slim/request`
- `Slim/Control/Jive.pm` - Jive-Menüsystem, `menustatus`
- `jive/net/Comet.lua` (JiveLite) - Client-Seite des Protokolls

## TODO - Offene Punkte

### Muss noch getestet werden
1. **Live-Test** mit Server nach allen Fixes
2. **Menu-Ergebnis prüfen** - Wird es jetzt auf dem Streaming-Channel gesendet?
3. **Boom UI testen** - Zeigt sie das Menü an?

### Potenzielle Probleme
1. **Streaming-Verbindung vs. Request-Verbindung**: Die `/slim/request` kommt auf einer separaten HTTP-Verbindung (Port 53459), aber das Event muss auf der Streaming-Verbindung (Port 53458) ankommen. Der Fix fügt Events zum Client hinzu und weckt den Waiter - aber funktioniert das auch über Verbindungsgrenzen hinweg?

2. **Event-Delivery Timing**: Wird das Event rechtzeitig gesendet bevor die Boom aufgibt?

3. **menustatus Subscription**: Der Stub gibt nur `{}` zurück. Falls die Boom echte Menu-Updates erwartet, könnte das ein Problem sein.

### Code-Review needed
- `resonance/web/cometd.py`: `slim_subscribe()` und `slim_request()` - Event-Delivery prüfen
- `resonance/web/routes/cometd.py`: clientId-Extraktion für alle `/slim/*` Channels

### Fehlende Features (niedrige Priorität)
- `menustatus` Notifications für dynamische Menü-Plugins
- Alarm/Sleep/Sync Settings (aktuell nur Stubs)

## Captures

| Datei | Inhalt |
|-------|--------|
| `tests/ws.pcapng` | Erste Capture |
| `tests/ws2.pcapng` | clientId-Problem gefunden |
| `tests/ws3.pcapng` | Nach clientId-Fix |
| `tests/ws4pcapng.pcapng` | Nach slim_subscribe-Fix, menustatus fehlt |

---

## Session 2026-02-06: Slimproto & Cometd Fixes

### Problem 1: Radio verbindet sich nicht nach HELO

**Symptom:** Squeezebox Radio sendet HELO, Server antwortet, aber Radio macht nie HTTP/Cometd-Verbindung zu Port 9000.

**Ursache:** Server sendete nach HELO falsche Nachrichten:
- `vers` (Server-Version)
- `setd 0x00 + player_id`
- `strm t` (status request)

**LMS sendet stattdessen:**
- `strm q` (query/stop)
- `setd 0x00` (nur Typ-Byte)
- `setd 0x04` (Firmware-Check)
- `aude 0x01 0x01` (Audio enable)
- `audg` (Volume/Gain)

**Fix:** `resonance/protocol/slimproto.py` - `_send_server_capabilities()` umgeschrieben.

### Problem 2: `/meta/reconnect` nicht unterstützt

**Symptom:** Radio sendet `/meta/reconnect` statt `/meta/connect`, Server antwortet mit "Unknown channel".

**Ursache:** Cometd-Router kannte nur `/meta/connect`.

**Fix:** `resonance/web/routes/cometd.py` - `/meta/reconnect` als Alias für `/meta/connect` hinzugefügt, inkl. Auto-Create des Clients bei Reconnect.

### Problem 3: `firmwareupgrade` Response falsch

**Symptom:** Radio zeigt "Resonance muss auf eine neue Version von LMS aktualisiert werden".

**Ursache:** Response hatte falsche Feldnamen:
```python
# Falsch:
{"relativeFirmwareUrl": "", "firmwareVersion": "", "firmwareUrl": "", "isUpgradeAvailable": 0}

# Richtig (wie LMS):
{"firmwareUpgrade": 0}
```

**Fix:** `resonance/web/handlers/menu.py` - `cmd_firmwareupgrade()` korrigiert.

### Problem 4: `Unknown client ID` bei `/slim/request`

**Symptom:** Server antwortet mit "Unknown client ID" wenn Radio `/slim/request` sendet.

**Ursache:** Radio sendet `clientId` nur im `data.response`-Pfad (z.B. `/7a6364c4/slim/request`), nicht als explizites Feld. Nach Server-Restart ist die Session unbekannt.

**Fix:** `resonance/web/cometd.py` - Auto-Create von Cometd-Clients bei `/slim/subscribe`, `/slim/unsubscribe`, `/slim/request` wenn clientId aus Response-Channel extrahiert wurde.

### Aktueller Stand

- Radio findet Resonance per Discovery ✅
- Radio macht Cometd-Handshake (`/meta/handshake`) ✅
- Radio macht Streaming-Connect (`/meta/connect` oder `/meta/reconnect`) ✅
- Radio subscribed zu `/clientId/**` ✅
- Radio subscribed zu `serverstatus` und `firmwarestatus` ✅

**Noch offen:**
- Radio zeigt immer noch "muss aktualisiert werden" — möglicherweise fehlt etwas in der `serverstatus` Response oder im `/meta/handshake`

### Wireshark-Captures

| Datei | Inhalt |
|-------|--------|
| `ws6.pcapng` | Slimproto-Traffic, kein HTTP (falscher Filter) |
| `ws11.pcapng` | Nach Slimproto-Fix, falscher Capture-Filter |
| `ws12.pcapng` | Cometd `/meta/reconnect` Fehler |
| `ws14.pcapng` | Nach reconnect-Fix, Streaming funktioniert |
| `lms.pcap` | LMS-Referenz-Capture (tcpdump auf Server) |

### LMS vs. Resonance Vergleich (aus lms.pcap)

**LMS Handshake-Response:**
```json
{
  "id": "",
  "channel": "/meta/handshake",
  "supportedConnectionTypes": ["long-polling", "streaming"],
  "successful": true,
  "clientId": "4444e3f2",
  "advice": {"timeout": 60000, "reconnect": "retry", "interval": 0},
  "version": "1.0"
}
```

**Resonance Handshake-Response:**
```json
{
  "channel": "/meta/handshake",
  "successful": true,
  "clientId": "5404e146",
  "version": "1.0",
  "supportedConnectionTypes": ["streaming", "long-polling"],
  "advice": {"reconnect": "retry", "interval": 0, "timeout": 60000}
}
```

Unterschiede:
- LMS hat `"id": ""` — Resonance fehlt dieses Feld
- LMS Server-Header: `Lyrion Music Server (9.0.3 - 1754981228)`

---

## TODO / Noch zu erledigen

### Kritisch für Boom-Funktionalität

1. **Live-Test durchführen**
   - Server neu starten mit allen Fixes
   - Boom einschalten und Verbindung prüfen
   - Neues Wireshark-Capture machen (ws5.pcapng)

2. **Menu-Ergebnis auf Streaming-Channel verifizieren**
   - Im Capture prüfen: Kommt `/7a6364c4/slim/request` mit Menu-Daten?
   - Falls nicht: Debug-Logging in `slim_request()` prüfen

3. **Boom UI prüfen**
   - Zeigt sie "My Music", "Radio", etc.?
   - Funktioniert Navigation in Untermenüs?

### Bekannte Lücken

- **`menustatus` ist nur ein Stub** - Gibt leeres Dict zurück
  - Für dynamische Menü-Updates (Plugins) müsste das erweitert werden
  - Für Basis-Funktionalität reicht der Stub

- **Subscriptions mit `subscribe:N`** werden nicht periodisch ausgeführt
  - LMS führt z.B. `serverstatus` alle 60 Sekunden erneut aus
  - Wir registrieren nur die Subscription, führen aber keine periodischen Updates durch

### Offene Fragen

- Warum pollt Boom Discovery so aggressiv (~1x/Sekunde)?
  - Normales Verhalten für Failover-Erkennung?
  - Oder Zeichen, dass etwas nicht stimmt?

- Connection-Timeout der Streaming-Verbindung
  - Wir haben 5 Minuten Timeout + 30s Heartbeat
  - Ist das kompatibel mit Boom-Erwartungen?