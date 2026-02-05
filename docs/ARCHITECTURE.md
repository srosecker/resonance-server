# 🎵 Resonance — Architektur

Python-Neuimplementierung des Logitech Media Server (LMS/SlimServer).

---

## 📋 Überblick

**Resonance** ist ein Server, der Squeezebox-Player und Software-Player (Squeezelite) steuert.

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Web-UI /   │ ◄──► │  Resonance  │ ◄──► │ Squeezelite │ ──► 🔊
│  Mobile App │ HTTP │   Server    │Slim- │  (Player)   │
│  Cadence    │      │             │proto │             │
└─────────────┘      └─────────────┘      └─────────────┘
```

**Wichtig:** Der Server gibt Befehle, Player sind "dumm" und führen aus.

---

## 🏗️ System-Architektur

### Das UI - Vermittler - Server Modell

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│       UI        │     │    VERMITTLER   │     │     SERVER      │
│  (Präsentation) │◀───▶│  (API/Adapter)  │◀───▶│  (Business Logic)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Vermittler-Übersicht

| Vermittler | UI | Protokoll |
|------------|-----|-----------|
| **Squeezelite** | Lautsprecher | Slimproto + HTTP Audio |
| **Web-Layer** | Browser | HTTP + JSON-RPC |
| **Cadence** | Desktop App | JSON-RPC |
| **Mobile Apps** | Smartphone | JSON-RPC + Cometd |

---

## 📂 Projektstruktur

```
resonance-server/
├── resonance/                    # Hauptpaket (~18.500 LOC)
│   ├── __init__.py
│   ├── __main__.py               # Entry: python -m resonance
│   ├── server.py                 # Haupt-Server, startet alle Komponenten
│   │
│   ├── config/                   # Konfiguration
│   │   ├── devices.toml          # Device-Tiers (Modern/Legacy)
│   │   └── legacy.conf           # Transcoding-Regeln (LMS-Stil)
│   │
│   ├── core/                     # Business Logic
│   │   ├── library.py            # MusicLibrary Facade
│   │   ├── library_db.py         # SQLite + aiosqlite
│   │   ├── scanner.py            # Audio-Datei Scanner (mutagen)
│   │   ├── playlist.py           # Playlist & PlaylistManager
│   │   ├── artwork.py            # Cover Art + BlurHash
│   │   ├── events.py             # Event-Bus (pub/sub)
│   │   └── db/                   # DB Schema & Queries
│   │       ├── models.py         # Dataclasses (Track, Album, Artist)
│   │       ├── schema.py         # SQLite Schema v8
│   │       ├── queries_*.py      # Query-Module
│   │       └── ordering.py       # Sort-Logik
│   │
│   ├── player/                   # Player-Verwaltung
│   │   ├── client.py             # PlayerClient (Status, Commands)
│   │   └── registry.py           # PlayerRegistry (alle Player)
│   │
│   ├── protocol/                 # Slimproto-Protokoll
│   │   ├── slimproto.py          # SlimprotoServer (Port 3483)
│   │   └── commands.py           # strm, audg, aude Builder
│   │
│   ├── streaming/                # Audio-Streaming
│   │   ├── server.py             # StreamingServer, start_offset
│   │   ├── transcoder.py         # Transcoding Pipeline (faad, flac, lame)
│   │   ├── seek_coordinator.py   # Latest-Wins Seek-Koordination
│   │   └── policy.py             # Transcoding-Entscheidungen
│   │
│   └── web/                      # HTTP/API Layer
│       ├── server.py             # FastAPI App (Port 9000)
│       ├── jsonrpc.py            # JSON-RPC Handler (/jsonrpc.js)
│       ├── jsonrpc_helpers.py    # Parameter-Parsing
│       ├── cometd.py             # Bayeux Long-Polling
│       ├── handlers/             # Command Handlers
│       │   ├── status.py         # Player-Status
│       │   ├── seeking.py        # Seek-Befehle (non-blocking!)
│       │   ├── playback.py       # Play/Pause/Stop
│       │   ├── playlist.py       # Queue-Befehle
│       │   └── library.py        # Library-Abfragen
│       └── routes/               # FastAPI Routes
│           ├── api.py            # REST Endpoints
│           ├── streaming.py      # /stream.mp3
│           ├── artwork.py        # Cover Art Endpoints
│           └── cometd.py         # /cometd
│
├── tests/                        # Tests (~6.400 LOC, 316 Tests)
├── web-ui/                       # Svelte 5 Frontend
│   └── src/
│       ├── lib/
│       │   ├── api.ts            # TypeScript JSON-RPC Client
│       │   ├── stores/           # Svelte 5 Runes Stores
│       │   └── components/       # UI-Komponenten
│       └── routes/               # SvelteKit Pages
└── docs/                         # Dokumentation
```

---

## 📡 Protokolle & Ports

| Port | Protokoll | Zweck |
|------|-----------|-------|
| **3483** | Slimproto (TCP) | Player-Steuerung (binär) |
| **9000** | HTTP | Streaming + JSON-RPC + Web-UI |

### Slimproto (Port 3483)

Binäres TCP-Protokoll zwischen Server und Player.

**Message-Format:**
```
┌──────────────┬──────────────┬─────────────────┐
│ Command      │ Length       │ Payload         │
│ (4 Bytes)    │ (4 Bytes)    │ (Length Bytes)  │
└──────────────┴──────────────┴─────────────────┘
```

**Wichtige Messages:**

| Tag | Richtung | Beschreibung |
|-----|----------|--------------|
| `HELO` | Client→Server | Handshake, Device-Info |
| `STAT` | Client→Server | Heartbeat, Status |
| `strm` | Server→Client | Stream-Control (start/pause/stop) |
| `audg` | Server→Client | Volume |

**STM Event Codes (in STAT):**

| Code | Bedeutung | Aktion |
|------|-----------|--------|
| `STMs` | Track Started | → PLAYING |
| `STMp` | Paused | → PAUSED |
| `STMr` | Resumed | → PLAYING |
| `STMf` | Flushed | → **Kein State-Change!** |
| `STMu` | Underrun | → STOPPED + Track-Finished |

### HTTP (Port 9000)

| Endpoint | Zweck |
|----------|-------|
| `POST /jsonrpc.js` | JSON-RPC API (LMS-kompatibel) |
| `GET /stream.mp3` | Audio-Streaming |
| `POST /cometd` | Real-Time Updates (Long-Polling) |
| `GET /api/*` | REST API |
| `GET /api/artwork/*` | Cover Art |

---

## 🎵 Audio-Pipeline

### Streaming-Flow

```
1. Client sendet "playlist play /path/to/song.mp3"
2. Server queued Track in StreamingServer
3. Server sendet `strm s` (start) an Player mit HTTP-URL
4. Player öffnet HTTP-Verbindung zu /stream.mp3
5. StreamingServer liefert Audio (direct oder transcoded)
6. Player reportet Status via STAT
```

### Transcoding

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│ M4B/M4A │───►│  faad   │───►│  flac   │───► Player
│  File   │    │ Decoder │    │ Encoder │
└─────────┘    └─────────┘    └─────────┘
```

**Entscheidungslogik:** `streaming/policy.py`

| Format | Aktion |
|--------|--------|
| MP3, FLAC, OGG, WAV | Direct Streaming |
| M4A, M4B, AAC | Transcode via faad→flac |

### Seek-Koordination

Problem: Rapid Seeks führen zu Race Conditions.

Lösung: `SeekCoordinator` mit Latest-Wins-Semantik.

```python
# Jeder Seek erhöht Generation
# Nur der letzte Seek wird ausgeführt
# 50ms Coalescing für schnelle aufeinanderfolgende Seeks
```

### Elapsed-Berechnung (LMS-konform)

Nach einem Seek reportet der Player `elapsed` relativ zum Stream-Start:

```python
# Formel (wie LMS):
elapsed = start_offset + raw_elapsed

# Beispiel: Seek zu 30s
# Player reportet: 0, 1, 2, 3...
# Server berechnet: 30+0=30, 30+1=31, 30+2=32...
```

---

## 🌐 Web-Layer Architektur

### FastAPI + JSON-RPC

```
Browser/App Request
      │
      ▼
┌─────────────────────────────────────────────────────┐
│                  FastAPI (Port 9000)                 │
│                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │ Static/UI   │  │ JSON-RPC    │  │ Cometd       │ │
│  │ (SvelteKit) │  │ (/jsonrpc)  │  │ (Real-Time)  │ │
│  └─────────────┘  └─────────────┘  └──────────────┘ │
└───────────────────────────┬─────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────┐
│              Command Handlers                        │
│  status.py | playback.py | playlist.py | seeking.py │
└───────────────────────────┬─────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────┐
│              Core Services                           │
│  MusicLibrary | Playlist | PlayerRegistry            │
└─────────────────────────────────────────────────────┘
```

### JSON-RPC Format (LMS-kompatibel)

```json
{
  "id": 1,
  "method": "slim.request",
  "params": [
    "aa:bb:cc:dd:ee:ff",
    ["playlist", "play", "/path/to/song.mp3"]
  ]
}
```

### Cometd/Bayeux

Long-Polling für Real-Time Updates (iPeng, Squeezer, etc.):

- `/meta/handshake` — Session erstellen
- `/meta/connect` — Events abholen (60s Timeout)
- `/slim/subscribe` — Player-Events abonnieren

---

## 🗄️ Datenbank

### SQLite mit aiosqlite

**Schema (v8):**

```sql
-- Kern-Tabellen
tracks (id, url, title, artist_id, album_id, duration_ms, ...)
artists (id, name)
albums (id, title, artist_id, year, artwork_url)
genres (id, name)
contributors (id, name, role)

-- Verknüpfungen
track_genres (track_id, genre_id)
track_contributors (track_id, contributor_id, role)
```

### Library Facade

```python
# Alle Library-Zugriffe über MusicLibrary Klasse:
library = MusicLibrary(db_path)
await library.scan_directory("/music")
artists = await library.list_artists()
tracks = await library.search("Beatles")
```

---

## 🎨 Frontend (Web-UI)

### Tech Stack

- **Svelte 5** mit Runes ($state, $derived)
- **SvelteKit** für Routing
- **Tailwind CSS v4**
- **TypeScript**

### State Management

```typescript
// Svelte 5 Runes Store
let status = $state<PlayerStatus | null>(null);
let playlist = $state<Track[]>([]);

// Derived State
let isPlaying = $derived(status?.mode === 'play');
```

### Komponenten

| Komponente | Funktion |
|------------|----------|
| `NowPlaying.svelte` | Album Art, Progress, Controls |
| `TrackList.svelte` | Track-Liste mit Actions |
| `Queue.svelte` | Playlist-Sidebar |
| `PlayerSelector.svelte` | Player-Auswahl |
| `CoverArt.svelte` | Cover mit BlurHash |

---

## 📱 Cadence (Flutter App)

### Architektur

```
cadence/lib/
├── api/
│   └── resonance_client.dart   # HTTP + JSON-RPC
├── providers/
│   └── providers.dart          # Riverpod State
├── models/
│   ├── player.dart
│   ├── track.dart
│   └── library.dart
├── screens/
│   ├── home_screen.dart
│   ├── library_screen.dart
│   └── queue_screen.dart
└── widgets/
    └── smooth_progress_slider.dart
```

### State Management

Riverpod mit `NowPlayingNotifier`:
- Polling alle 1s für Status
- Optimistic Updates für UI-Responsiveness
- Recovery bei Timeouts

---

## 🔧 Technologie-Stack

| Komponente | Technologie |
|------------|-------------|
| **Runtime** | Python 3.11+ (asyncio) |
| **Web Framework** | FastAPI |
| **Datenbank** | SQLite + aiosqlite |
| **Audio-Metadaten** | mutagen |
| **Transcoding** | faad, flac, lame, sox |
| **Frontend** | Svelte 5 + Tailwind v4 |
| **Desktop App** | Flutter + Riverpod |
| **Testing** | pytest |

---

## 📚 Verwandte Dokumente

- [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md) — Quick Reference für AI
- [SLIMPROTO.md](./SLIMPROTO.md) — Protokoll-Details
- [SEEK_ELAPSED_FINDINGS.md](./SEEK_ELAPSED_FINDINGS.md) — Seek-Implementierung
- [COMPARISON_LMS.md](./COMPARISON_LMS.md) — Feature-Vergleich mit LMS
- [E2E_TEST_GUIDE.md](./E2E_TEST_GUIDE.md) — Test-Anleitung

---

*Zuletzt aktualisiert: Februar 2026*