# 🎵 Squeezebox Radio/Touch/Boom — Protokoll-Dokumentation

> **Erkenntnisse aus der Debugging-Session Februar 2026**
> Diese Dokumentation beschreibt, wie Squeezebox-Hardware (Radio, Touch, Boom) mit dem Resonance-Server kommuniziert.

---

## 📡 Übersicht: Die drei Kommunikationskanäle

Squeezebox-Geräte nutzen **drei parallele Verbindungen** zum Server:

```
┌─────────────────┐         ┌─────────────────┐
│  Squeezebox     │         │   Resonance     │
│  Radio/Boom     │         │   Server        │
│                 │         │                 │
│  ┌───────────┐  │  UDP    │  ┌───────────┐  │
│  │ Discovery │──┼────────►│  │ Discovery │  │  Port 3483 UDP
│  │ Client    │◄─┼─────────│  │ Server    │  │  (Broadcast)
│  └───────────┘  │         │  └───────────┘  │
│                 │         │                 │
│  ┌───────────┐  │  TCP    │  ┌───────────┐  │
│  │ Slimproto │◄─┼────────►│  │ Slimproto │  │  Port 3483 TCP
│  │ Client    │  │         │  │ Server    │  │  (Binärprotokoll)
│  └───────────┘  │         │  └───────────┘  │
│                 │         │                 │
│  ┌───────────┐  │  HTTP   │  ┌───────────┐  │
│  │ Cometd/   │◄─┼────────►│  │ FastAPI   │  │  Port 9000 HTTP
│  │ SqueezePlay│  │         │  │ WebServer │  │  (JSON-RPC, Streaming)
│  └───────────┘  │         │  └───────────┘  │
└─────────────────┘         └─────────────────┘
```

| Kanal | Port | Protokoll | Zweck |
|-------|------|-----------|-------|
| **Discovery** | 3483 UDP | TLV-basiert | Server finden, IP/Port/UUID austauschen |
| **Slimproto** | 3483 TCP | Binär | Player-Steuerung, Audio-Streaming-Befehle |
| **HTTP/Cometd** | 9000 TCP | JSON-RPC | Menüs, Bibliothek, Real-Time-Updates |

---

## 1️⃣ Discovery-Protokoll (UDP Port 3483)

### Ablauf

1. Gerät sendet **Broadcast** an `255.255.255.255:3483`
2. Server antwortet mit **TLV-Response** (direkt an Gerät-IP)
3. Gerät extrahiert Server-IP, Port, UUID, Version

### TLV-Format (Type-Length-Value)

```
┌──────┬──────┬───────────────┐
│ Type │ Len  │ Value         │
│ 4B   │ 1B   │ Len Bytes     │
└──────┴──────┴───────────────┘
```

### Wichtige TLVs

| TLV Code | Name | Beispiel | Beschreibung |
|----------|------|----------|--------------|
| `IPAD` | IP Address | `192.168.1.30` | Server-IP (4 Bytes binär) |
| `NAME` | Server Name | `Resonance` | Anzeigename |
| `JSON` | HTTP Port | `9000` | Port als ASCII-String! |
| `VERS` | Version | `7.999.999` | **KRITISCH**: Muss 7.x sein! |
| `UUID` | Server UUID | `6bab33eb-01ca-4ceb-9553-8285ddc9b2e9` | 36 Zeichen UUID v4 |
| `JVID` | Jive Device ID | MAC-Adresse | Identifiziert Touch-UI-Gerät |

### Kritische Erkenntnisse

**VERS muss 7.x sein!**
```
❌ "9.0.0"      → Firmware-Bug: wird als "zu alt" abgelehnt
❌ "8.0.0"      → Firmware-Bug: wird als "zu alt" abgelehnt  
✅ "7.999.999"  → LMS-Trick: RADIO_COMPATIBLE_VERSION
✅ "7.9.1"      → Funktioniert auch
```

**UUID muss vollständig sein!**
```
❌ "db2d3683"                                → 8 Zeichen = FAIL
✅ "6bab33eb-01ca-4ceb-9553-8285ddc9b2e9"   → 36 Zeichen = OK
```

### Resonance-Implementierung

```python
# resonance/protocol/discovery.py
class DiscoveryServer:
    async def handle_request(self, data, addr):
        # Parse angeforderte TLVs
        requested_tlvs = self._parse_tlv_request(data)
        
        # Baue Response mit korrekter Server-IP
        server_ip = self._get_local_ip_for_client(addr[0])
        
        response = self._build_tlv_response({
            'IPAD': server_ip,
            'NAME': 'Resonance',
            'JSON': '9000',           # ASCII String!
            'VERS': '7.999.999',      # Firmware-kompatibel
            'UUID': self.server_uuid,  # 36 Zeichen
        })
```

---

## 2️⃣ Slimproto-Protokoll (TCP Port 3483)

### Nachrichtenformat

```
┌──────────┬──────────┬─────────────────┐
│ Command  │ Length   │ Payload         │
│ 4 Bytes  │ 4 Bytes  │ Length Bytes    │
│ ASCII    │ Big-End  │                 │
└──────────┴──────────┴─────────────────┘
```

### Verbindungsaufbau

```
Client (Radio)                    Server (Resonance)
     │                                  │
     │──────── TCP Connect ────────────►│
     │                                  │
     │──────── HELO ───────────────────►│  Player identifiziert sich
     │                                  │
     │◄─────── vers ───────────────────│  "7.999.999"
     │◄─────── strm q ─────────────────│  Status-Query
     │◄─────── setd 0x00 ──────────────│  Player-ID-Type
     │◄─────── setd 0x04 ──────────────│  Firmware-Check
     │◄─────── aude ───────────────────│  Audio Enable
     │◄─────── audg ───────────────────│  Volume/Gain
     │                                  │
     │──────── STAT STMt ──────────────►│  Status-Response
     │                                  │
     │         ... Heartbeat Loop ...   │
     │                                  │
```

### Wichtige Befehle (Server → Client)

| Befehl | Beschreibung | Payload |
|--------|--------------|---------|
| `vers` | Server-Version | `"7.999.999"` (UTF-8) |
| `strm` | Stream-Kontrolle | Siehe unten |
| `audg` | Volume/Gain | 18+ Bytes |
| `aude` | Audio Enable | 2 Bytes (SPDIF, DAC) |
| `setd` | Device Settings | Variabel |

### `strm` Befehl im Detail

```
Byte 0:  Command ('s'=start, 'p'=pause, 'u'=unpause, 'q'=query, 't'=status)
Byte 1:  Autostart ('0'=off, '1'=on, '2'=direct, '3'=direct+auto)
Byte 2:  Format ('m'=mp3, 'f'=flac, 'o'=ogg, 'p'=pcm)
Byte 3:  PCM Sample Size
Byte 4:  PCM Sample Rate
Byte 5:  PCM Channels
Byte 6:  PCM Endianness
Byte 7:  Threshold
Byte 8:  SPDIF Enable
Byte 9:  Transition Period
Byte 10: Transition Type
Byte 11: Flags
Byte 12: Output Threshold
Byte 13: Reserved
Byte 14-15: Replay Gain (16-bit)
Byte 16-17: Server Port (16-bit, Big Endian)
Byte 18-21: Server IP (32-bit, Big Endian)
Byte 22+: HTTP Request String (für 's' command)
```

### Wichtige Nachrichten (Client → Server)

| Nachricht | Beschreibung |
|-----------|--------------|
| `HELO` | Hello - Player-Identifikation (MAC, Device-Type, Firmware) |
| `STAT` | Status-Report mit Event-Code |
| `IR  ` | IR-Fernbedienung (4 Bytes + Padding) |
| `BYE!` | Disconnect |
| `RESP` | HTTP Response Header |
| `META` | Metadata |
| `BODY` | HTTP Body |
| `DSCO` | Disconnect Reason |

### STAT Event-Codes

| Event | Bedeutung | Server-Aktion |
|-------|-----------|---------------|
| `STMt` | Heartbeat/Timer | Keine |
| `STMs` | Track **S**tarted | → PLAYING |
| `STMp` | **P**aused | → PAUSED |
| `STMr` | **R**esumed | → PLAYING |
| `STMf` | **F**lushed | Kein State-Change! |
| `STMd` | **D**ecode Ready | Kein Auto-Advance! |
| `STMu` | **U**nderrun | → STOPPED + Track-Finished |

**Wichtig:** Nur `STMu` triggert Track-Finished/Auto-Advance!

### TCP Keepalive (Windows-Fix)

```python
# resonance/protocol/slimproto.py
async def _handle_connection(self, reader, writer):
    sock = writer.get_extra_info("socket")
    if sock is not None:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "SIO_KEEPALIVE_VALS"):
            # (onoff=1, keepalive_time=10000ms, keepalive_interval=5000ms)
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 5000))
```

Ohne Keepalive: `WinError 121` (Semaphore-Timeout) nach ~20 Sekunden Inaktivität.

---

## 3️⃣ HTTP/Cometd-Protokoll (Port 9000)

### Cometd/Bayeux Handshake

```
Client                              Server
  │                                   │
  │── POST /cometd ──────────────────►│
  │   /meta/handshake                 │
  │   supportedConnectionTypes:       │
  │   ["streaming"]                   │
  │                                   │
  │◄─────────────────────────────────│
  │   clientId: "b683799c"            │
  │   supportedConnectionTypes:       │
  │   ["streaming", "long-polling"]   │
  │                                   │
  │── POST /cometd ──────────────────►│
  │   /meta/connect                   │
  │   connectionType: "streaming"     │
  │                                   │
  │◄═════════════════════════════════│  Streaming-Response
  │   (chunked transfer encoding)     │  (Connection bleibt offen)
  │                                   │
```

### JSON-RPC Format

```json
[{
  "id": 9,
  "data": {
    "request": ["00:04:20:26:84:ae", ["browselibrary", "items", 0, 200, "mode:albums"]],
    "response": "/418e82f6/slim/request"
  },
  "channel": "/slim/request"
}]
```

### Wichtige Channels

| Channel | Beschreibung |
|---------|--------------|
| `/meta/handshake` | Verbindungsaufbau |
| `/meta/connect` | Keep-Alive |
| `/meta/subscribe` | Event-Subscription |
| `/slim/request` | JSON-RPC Befehle |
| `/slim/subscribe` | Status-Subscriptions |
| `/{clientId}/slim/serverstatus` | Server-Status Events |
| `/{clientId}/slim/playerstatus/{mac}` | Player-Status Events |

---

## 4️⃣ Menü-System (Jive/SqueezePlay)

### Browse-Hierarchie

```
Hauptmenü (menu)
├── Meine Musik
│   ├── Alben (browselibrary mode:albums)
│   │   └── Album X (browselibrary mode:tracks album_id:3)
│   │       └── Track Y → playlistcontrol cmd:load track_id:169
│   ├── Künstler (browselibrary mode:artists)
│   ├── Genres (browselibrary mode:genres)
│   └── Jahre (browselibrary mode:years)
├── Wiedergabeliste
└── Einstellungen
```

### Menu Item Format

```json
{
  "text": "Der stille Freund",
  "id": "album_3",
  "textkey": "D",
  "icon-id": 3,
  "icon": "http://192.168.1.30:9000/artwork/3",
  "actions": {
    "go": {
      "cmd": ["browselibrary", "items"],
      "params": {"menu": 1, "mode": "tracks", "album_id": 3}
    },
    "play": {
      "player": 0,
      "cmd": ["playlistcontrol"],
      "params": {"cmd": "load", "album_id": 3}
    },
    "add": {
      "player": 0,
      "cmd": ["playlistcontrol"],
      "params": {"cmd": "add", "album_id": 3}
    }
  }
}
```

### Track Item Format

```json
{
  "text": "Vorspann - Der stille Freund",
  "id": "track_169",
  "type": "audio",
  "playAction": "play",
  "goAction": "play",
  "nextWindow": "nowPlaying",
  "textkey": "V",
  "actions": {
    "go": {
      "player": 0,
      "cmd": ["playlistcontrol"],
      "params": {"cmd": "load", "track_id": 169},
      "nextWindow": "nowPlaying"
    },
    "play": {
      "player": 0,
      "cmd": ["playlistcontrol"],
      "params": {"cmd": "load", "track_id": 169},
      "nextWindow": "nowPlaying"
    },
    "add": {
      "player": 0,
      "cmd": ["playlistcontrol"],
      "params": {"cmd": "add", "track_id": 169}
    },
    "add-hold": {
      "player": 0,
      "cmd": ["playlistcontrol"],
      "params": {"cmd": "insert", "track_id": 169}
    }
  }
}
```

> ⚠️ **WICHTIG:** SqueezePlay verwendet die `"go"` Action bei Enter/OK, NICHT `"play"`!
> Ohne explizite `"go"` Action passiert beim Drücken von Enter nichts.

### Kritische Felder

| Feld | Beschreibung | Wichtig für |
|------|--------------|-------------|
| `icon` | Vollständige URL | Cover-Anzeige |
| `icon-id` | Artwork-ID (z.B. `/music/{album_id}/cover`) | Alternative zu `icon` |
| `type: "audio"` | Markiert abspielbaren Inhalt | Play-Button |
| `playAction: "play"` | Default-Aktion beim Tippen | Touch-Verhalten |
| `goAction: "play"` | Was bei Enter/OK passiert | **Pflicht für Tracks!** |
| `nextWindow: "nowPlaying"` | Wohin nach Aktion navigieren | Now Playing Anzeige |
| `actions.go` | **Enter/OK-Befehl** | **Pflicht für Tracks!** |
| `actions.play` | Play-Befehl | Abspielen |

---

## 5️⃣ Song abspielen — Kompletter Flow

### Schritt 1: User wählt Track im Menü

```
Radio UI: Tippe auf "Vorspann - Der stille Freund"
```

### Schritt 2: HTTP Request (Cometd)

```json
POST /cometd
[{
  "id": 11,
  "data": {
    "request": ["00:04:20:26:84:ae", 
      ["playlistcontrol", "cmd:load", "track_id:169", "useContextMenu:1"]
    ],
    "response": "/b683799c/slim/request"
  },
  "channel": "/slim/request"
}]
```

### Schritt 3: Server verarbeitet `playlistcontrol`

```python
# resonance/web/handlers/menu.py
async def cmd_playlistcontrol(ctx, command):
    params = parse_params(command)  # {"cmd": "load", "track_id": "169"}
    
    # Weiterleitung an playlist handler
    playlist_cmd = ["playlist", "loadtracks", "track_id:169"]
    return await cmd_playlist(ctx, playlist_cmd)
```

### Schritt 4: Playlist laden + Stream starten

```python
# resonance/web/handlers/playlist.py
async def _playlist_loadtracks(ctx, params):
    # 1. Alte Playlist/Stream stoppen
    playlist.clear()
    streaming_server.cancel_stream(player_id)
    await player.stop()
    
    # 2. Track aus DB laden
    track = await db.get_track_by_id(169)
    playlist.add(track)
    
    # 3. Stream starten
    await _start_track_stream(ctx, player, track)
```

### Schritt 5: Stream zum Player senden

```python
# resonance/web/handlers/playlist.py
async def _start_track_stream(ctx, player, track):
    # 1. Transcoding vorbereiten
    streaming_server.queue_file(player_id, track.path)
    
    # 2. strm s (start) an Player senden
    await player.start_track(
        track,
        server_port=9000,
        server_ip="192.168.1.30"  # LAN-IP, nicht 127.0.0.1!
    )
```

### Schritt 6: Slimproto `strm s` Befehl

```
Server → Radio (TCP 3483):

strm s 1 m ? ? ? ? 255 0 0 0 0 0 0 0 0 35 16 192 168 1 30
     │ │ │                           │  │  └─────────────┘
     │ │ │                           │  │        Server IP
     │ │ │                           │  └─ Server Port (9000)
     │ │ │                           └─ Flags/Threshold
     │ │ └─ Format (m=mp3)
     │ └─ Autostart (1=on)
     └─ Command (s=start)

+ HTTP Request String:
  "GET /stream?player=00:04:20:26:84:ae HTTP/1.0\r\n\r\n"
```

### Schritt 7: Player holt Audio-Stream

```
Radio → Server (TCP 9000):

GET /stream?player=00:04:20:26:84:ae HTTP/1.0

Server → Radio:

HTTP/1.0 200 OK
Content-Type: audio/mpeg
Transfer-Encoding: chunked

[... MP3 Audio Data ...]
```

### Schritt 8: Player meldet Status

```
Radio → Server (TCP 3483):

STAT STMs ...   # Track Started → Server setzt State auf PLAYING
STAT STMt ...   # Heartbeat (alle 5 Sekunden)
STAT STMt ...
...
STAT STMu ...   # Underrun → Track Finished → Auto-Advance
```

---

## 6️⃣ Kritische Bugs & Fixes

### Bug A: 127.0.0.1 in URLs

**Problem:** Server meldete `"ip": "127.0.0.1"` — Radio konnte keine Ressourcen laden.

**Fix:** LAN-IP via UDP-Socket-Trick erkennen:

```python
def _detect_lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))  # Kein Paket wird gesendet!
        return s.getsockname()[0]   # z.B. "192.168.1.30"
```

### Bug B: Player Count 0

**Problem:** `serverstatus` meldete `"player count": 0` — Radio fand sich nicht.

**Ursache:** Bug C (TCP-Crash) → Player wurde deregistriert.

**Fix:** Löst sich durch Bug C Fix.

### Bug C: WinError 121

**Problem:** TCP-Verbindung crashte nach ~20s mit "Semaphore-Timeout".

**Fix:** TCP Keepalive aktivieren:

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 5000))
```

### Bug D: track_id nicht unterstützt

**Problem:** `playlistcontrol cmd:load track_id:169` → "No track criteria specified"

**Fix:** `track_id` Parameter in `_playlist_loadtracks` hinzugefügt:

```python
track_id = get_filter_int(tagged_params, "track_id")
if track_id is not None:
    row = await db.get_track_by_id(track_id)
    rows = [row] if row else []
```

### Bug E: UUID State-Gate

**Problem:** Radio macht Discovery, aber KEIN HTTP, wenn Server-UUID bekannt ist.

**Ursache:** SqueezePlay cached Server-UUID. Bei bekannter UUID → `_serverUpdateAddress()` → kein `connect()`.

**Workaround:** Server-UUID löschen: `rm cache/server_uuid`

**Langfristig:** Sicherstellen, dass Server beim ersten Kontakt korrekt antwortet.

### Bug F: Cover 404 bei `/music/{id}/cover`

**Problem:** Radio fordert `/music/3/cover_41x41_m` an → 404 "Track not found"

**Ursache:** Route behandelte ID als `track_id`, aber wir setzen `icon-id="/music/{album_id}/cover"`.

**Fix:** Route sucht jetzt zuerst nach `album_id`, dann als Fallback nach `track_id`:

```python
# Strategy 1: Try as album_id first
rows = await db.list_tracks_by_album(album_id=artwork_id, offset=0, limit=1)
if rows:
    track_path = rows[0].path

# Strategy 2: Fallback to track_id
if not track_path:
    row = await db.get_track_by_id(artwork_id)
    if row:
        track_path = row.path
```

### Bug G: Volume laggy / seq_no nicht unterstützt

**Problem:** Lautstärkeänderungen fühlten sich verzögert an.

**Ursache:** Der `seq_no` Parameter wurde nicht verarbeitet. LMS verwendet Sequenznummern, damit der Player veraltete Volume-Updates erkennen und ignorieren kann.

**Fix:** `seq_no` Support implementiert:

```python
# 1. cmd_mixer parst seq_no
seq_no = None
for param in params:
    if param.startswith("seq_no:"):
        seq_no = int(param.split(":", 1)[1])

# 2. set_volume gibt seq_no an audg Frame weiter
await player.set_volume(new_volume, seq_no=seq_no)

# 3. build_audg_frame fügt seq_no am Ende hinzu
if seq_no is not None:
    frame += struct.pack(">I", seq_no)

# 4. status Response gibt seq_no zurück
if player._seq_no is not None:
    result["seq_no"] = player._seq_no
```

### Bug H: "Aktuelle Wiedergabeliste" leer

**Problem:** Nach Track-Auswahl zeigt "Now Playing" eine leere Playlist.

**Ursache:** `playlist_loop` wurde nur aufgebaut wenn `current_track is not None`. Kurz nach dem Hinzufügen eines Tracks (aber vor Playback-Start) war `current_track` noch `None`.

**Fix:** `playlist_loop` Aufbau außerhalb des `if current is not None:` Blocks verschoben:

```python
if playlist is not None:
    result["playlist_tracks"] = len(playlist)
    
    current = playlist.current_track
    if current is not None:
        # ... currentTrack Infos ...
    
    # playlist_loop wird IMMER aufgebaut (außerhalb von if current)
    tracks = list(playlist.tracks)[start : start + items]
    for i, track in enumerate(tracks):
        playlist_loop.append(track_dict)
```

---

## 7️⃣ Dateien & Funktionen

### Discovery

| Datei | Funktion |
|-------|----------|
| `resonance/protocol/discovery.py` | `DiscoveryServer` |
| `resonance/protocol/discovery.py` | `_build_tlv_response()` |
| `resonance/protocol/discovery.py` | `_get_local_ip_for_client()` |

### Slimproto

| Datei | Funktion |
|-------|----------|
| `resonance/protocol/slimproto.py` | `SlimprotoServer` |
| `resonance/protocol/slimproto.py` | `_handle_connection()` |
| `resonance/protocol/slimproto.py` | `_send_server_capabilities()` |
| `resonance/protocol/slimproto.py` | `_message_loop()` |
| `resonance/protocol/commands.py` | `build_strm_frame()` |
| `resonance/player/client.py` | `PlayerClient.start_track()` |

### HTTP/Cometd

| Datei | Funktion |
|-------|----------|
| `resonance/web/server.py` | `WebServer` |
| `resonance/web/cometd.py` | `CometdManager` |
| `resonance/web/jsonrpc.py` | `JsonRpcHandler` |
| `resonance/web/routes/cometd.py` | Cometd-Endpoints |

### Menü-System

| Datei | Funktion |
|-------|----------|
| `resonance/web/handlers/menu.py` | `cmd_menu()` |
| `resonance/web/handlers/menu.py` | `cmd_browselibrary()` |
| `resonance/web/handlers/menu.py` | `cmd_playlistcontrol()` |
| `resonance/web/handlers/menu.py` | `_browse_albums()` |
| `resonance/web/handlers/menu.py` | `_browse_tracks()` |

### Playlist & Streaming

| Datei | Funktion |
|-------|----------|
| `resonance/web/handlers/playlist.py` | `cmd_playlist()` |
| `resonance/web/handlers/playlist.py` | `_playlist_loadtracks()` |
| `resonance/web/handlers/playlist.py` | `_start_track_stream()` |
| `resonance/streaming/server.py` | `StreamingServer` |
| `resonance/streaming/transcoder.py` | Audio-Transcoding |

---

## 8️⃣ Wireshark-Filter

```
# Alle Resonance-relevanten Pakete
tcp.port == 3483 || tcp.port == 9000 || udp.port == 3483

# Nur Discovery
udp.port == 3483

# Nur Slimproto
tcp.port == 3483

# Nur HTTP/Cometd
tcp.port == 9000

# HTTP Requests
http.request.method == POST

# Cometd-Requests
http.request.uri contains "/cometd"

# Streaming
http.request.uri contains "/stream"
```

---

## 9️⃣ Referenzen

| Quelle | Beschreibung |
|--------|--------------|
| `slimserver-public-9.1/` | Original LMS Perl-Code |
| `jivelite-master/` | SqueezePlay Lua UI-Code |
| `docs/LYRION_PROTOCOL_DOCS.md` | Gesammelte Lyrion-Dokumentation |
| `docs/SEEK_ELAPSED_FINDINGS.md` | Elapsed-Time-Berechnung |
| `docs/SLIMPROTO.md` | Binärprotokoll-Details |
| `docs/Research_gold.md` | Deep-Research-Ergebnisse |