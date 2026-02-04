# 🌐 Web-Interface Architektur

Diese Dokumentation beschreibt die UI-Vermittler-Server Architektur des Lyrion Music Server (LMS) und wie wir sie in Resonance umsetzen wollen.

---

## 📐 Das UI - Vermittler - Server Modell

### Grundprinzip

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│       UI        │     │    VERMITTLER   │     │     SERVER      │
│  (Präsentation) │◀───▶│  (API/Adapter)  │◀───▶│  (Business Logic)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

- **UI** = Was der Benutzer sieht und bedient
- **Vermittler** = Übersetzt zwischen UI und Server
- **Server** = Die eigentliche Logik und Daten

---

## 🎵 Szenario 1: Audio-Playback (bereits implementiert ✅)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│       UI        │     │    VERMITTLER   │     │     SERVER      │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│                 │     │                 │     │                 │
│  Lautsprecher   │◀────│  Squeezelite    │◀────│  Resonance      │
│  (Audio Output) │Audio│  - Decoder      │Slim-│  - SlimprotoSrv │
│                 │     │  - Audio Driver │proto│  - StreamingSrv │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Rollen:

| Komponente | Rolle | Was sie tut |
|------------|-------|-------------|
| **Resonance** | SERVER | Sendet Befehle (strm, audg) + Audio-Daten |
| **Squeezelite** | VERMITTLER | Empfängt Slimproto, decodiert Audio, gibt an Treiber |
| **Lautsprecher** | UI | Der Benutzer hört das Audio |

### Protokolle:
- Resonance → Squeezelite: **Slimproto** (Port 3483) + **HTTP Audio** (Port 9000)
- Squeezelite → Lautsprecher: **Audio-Treiber** (WASAPI, MME, ALSA, etc.)

---

## 🖥️ Szenario 2: Web-Interface (noch zu implementieren)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│       UI        │     │    VERMITTLER   │     │     SERVER      │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│                 │     │                 │     │                 │
│  Browser        │◀───▶│  Web-Layer      │◀───▶│  Core           │
│  (HTML/JS)      │HTTP │  - HTTP Router  │     │  - MusicLibrary │
│                 │     │  - JSON-RPC     │     │  - Playlist     │
│                 │     │  - WebSocket    │     │  - Scanner      │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Rollen:

| Komponente | Rolle | Was sie tut |
|------------|-------|-------------|
| **Core** | SERVER | Musikdatenbank, Playlist-Logik, Player-Registry |
| **Web-Layer** | VERMITTLER | HTTP-Server, JSON-RPC API, Template-Rendering |
| **Browser** | UI | HTML/CSS/JavaScript für den Benutzer |

---

## 📱 Szenario 3: Mobile Apps

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│       UI        │     │    VERMITTLER   │     │     SERVER      │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│                 │     │                 │     │                 │
│  Smartphone     │◀───▶│  Mobile App     │◀───▶│  Resonance      │
│  (Touchscreen)  │     │  (iPeng, etc.)  │JSON-│  - JSON-RPC API │
│                 │     │                 │RPC  │                 │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 🔄 Gesamtbild: Alle Vermittler

```
                              ┌─────────────────┐
                              │     SERVER      │
                              │   (Resonance)   │
                              │                 │
                              │  - SlimprotoSrv │
                              │  - StreamingSrv │
                              │  - MusicLibrary │
                              │  - Playlist     │
                              │  - JSON-RPC API │
                              └────────┬────────┘
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 │                     │                     │
                 ▼                     ▼                     ▼
        ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
        │   VERMITTLER   │    │   VERMITTLER   │    │   VERMITTLER   │
        │                │    │                │    │                │
        │  Squeezelite   │    │  Web-Layer     │    │  Mobile App    │
        │  (Decoder)     │    │  (HTTP/WS)     │    │  (iPeng etc.)  │
        └───────┬────────┘    └───────┬────────┘    └───────┬────────┘
                │                     │                     │
                ▼                     ▼                     ▼
        ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
        │       UI       │    │       UI       │    │       UI       │
        │                │    │                │    │                │
        │  Lautsprecher  │    │    Browser     │    │  Smartphone    │
        └────────────────┘    └────────────────┘    └────────────────┘
```

### Vermittler-Übersicht

| Vermittler | UI | Protokoll zum Server |
|------------|-----|---------------------|
| **Squeezelite** | Lautsprecher | Slimproto + HTTP Audio |
| **Web-Layer** | Browser | HTTP + JSON-RPC + WebSocket |
| **Mobile App** | Smartphone | JSON-RPC (über HTTP) |
| **Hardware Player** | Squeezebox-Display | Slimproto + Cometd |

---

## 🏗️ LMS Web-Layer Architektur (Original)

### Komponenten im Detail

```
Browser Request
      │
      ▼
┌─────────────────────────────────────────────────────────────┐
│                  Slim::Web::HTTP                             │
│                  (HTTP Server, Port 9000)                    │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Static Files│  │ Templates   │  │ Raw Functions       │  │
│  │ (HTML/JS/CSS│  │ (*.html)    │  │ (JSON-RPC, Cometd)  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Slim::Web::Pages                            │
│                  (URL → Handler Routing)                     │
│                                                              │
│  addPageFunction(qr/^home\.htm/, \&home);                   │
│  addRawFunction('jsonrpc.js', \&handleURI);                 │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Slim::Control::Request                          │
│              (Einheitliche Command-API)                      │
│                                                              │
│  Alle Befehle: ["player", ["command", "arg1", "arg2"]]      │
│  Egal ob von: Web, CLI, Telnet, JSON-RPC, Slimproto         │
└─────────────────────────────────────────────────────────────┘
```

### Wichtige Original-Dateien

| Datei | Funktion |
|-------|----------|
| `Slim/Web/HTTP.pm` | HTTP-Server Basis |
| `Slim/Web/Pages.pm` | URL-Routing |
| `Slim/Web/JSONRPC.pm` | JSON-RPC Endpoint (`/jsonrpc.js`) |
| `Slim/Web/Cometd.pm` | Push-Events (Long-Polling) |
| `Slim/Web/Pages/*.pm` | Einzelne Seiten-Handler |
| `Slim/Control/Request.pm` | Command-Parser |
| `HTML/*/` | Template-Dateien |

### JSON-RPC API

**Endpoint:** `POST /jsonrpc.js`

**Request Format:**
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

**Response Format:**
```json
{
  "id": 1,
  "method": "slim.request",
  "params": ["aa:bb:cc:dd:ee:ff", ["playlist", "play", "/path/to/song.mp3"]],
  "result": { ... }
}
```

---

## 🚀 Resonance Web-Layer Plan

### Technologie-Stack

| Komponente | LMS (Perl) | Resonance (Python) |
|------------|------------|-------------------|
| HTTP Server | HTTP::Daemon | **FastAPI** |
| Routing | Tie::RegexpHash | FastAPI Router |
| JSON-RPC | Custom | **jsonrpcserver** oder custom |
| Push-Events | Cometd | **WebSocket** |
| Templates | Template Toolkit | **Jinja2** oder SPA |
| Frontend | jQuery + Custom | **Vue.js** oder **React** |

### Geplante Struktur

```
resonance/
├── resonance/
│   ├── web/                    # Web-Layer (VERMITTLER) - ✅ IMPLEMENTIERT!
│   │   ├── __init__.py         # ✅ Package exports
│   │   ├── server.py           # ✅ FastAPI App + WebServer class
│   │   ├── jsonrpc.py          # ✅ JSON-RPC Handler (LMS-kompatibel)
│   │   ├── routes/
│   │   │   ├── __init__.py     # ✅ Package
│   │   │   ├── api.py          # ✅ REST API Endpoints
│   │   │   ├── jsonrpc.py      # ✅ JSON-RPC Route Registration
│   │   │   ├── streaming.py    # ✅ Streaming Route (/stream.mp3)
│   │   │   └── websocket.py    # TODO: WebSocket für Push
│   │   └── static/             # TODO: Frontend-Dateien
│   │
│   ├── core/                   # SERVER (Business Logic) - ✅ IMPLEMENTIERT!
│   │   ├── __init__.py         # ✅ Core exceptions
│   │   ├── library.py          # ✅ MusicLibrary Facade API
│   │   ├── library_db.py       # ✅ SQLite DB Layer (aiosqlite)
│   │   ├── scanner.py          # ✅ Audio file scanner (mutagen)
│   │   ├── playlist.py         # ✅ Playlist-Logik (Queue pro Player)
│   │   └── commands.py         # TODO: Command-Parser
│   │
│   ├── player/                 # Player-Verwaltung - ✅ IMPLEMENTIERT
│   └── protocol/               # Slimproto - ✅ IMPLEMENTIERT
```

---

## ✅ Aktueller Stand (Februar 2026)

**293/293 Tests bestanden ✅**

### Implementiert:
- [x] **Server:** SlimprotoServer, StreamingServer, PlayerRegistry
- [x] **Vermittler (Audio):** Squeezelite funktioniert
- [x] **UI (Audio):** Lautsprecher gibt Audio aus
- [x] **Core MusicLibrary:** Scanner, DB, Facade
  - `scanner.py` - Ordner scannen, Metadaten via `mutagen` extrahieren
  - `library_db.py` - SQLite + aiosqlite, WAL-Mode, Upsert, Search
  - `library.py` - High-Level API für Web/CLI
  - Unterstützte Formate: MP3, FLAC, OGG, Opus, M4A, M4B, AAC, WAV, AIFF, WMA
- [x] **Vermittler (Web):** FastAPI + JSON-RPC + REST API
  - `web/server.py` - FastAPI Application auf Port 9000
  - `web/jsonrpc.py` - JSON-RPC Handler (`/jsonrpc.js`)
  - `web/routes/api.py` - REST Endpoints (`/api/*`)
  - Commands: `serverstatus`, `players`, `status`, `artists`, `albums`, `titles`, `search`
  - LMS-kompatibel für iPeng, Squeezer, Material Skin, Orange Squeeze
- [x] **Playback Commands:** play, pause, stop, volume, power, mode, time, button
- [x] **Playlist-Integration:**
  - `core/playlist.py` - Playlist & PlaylistManager Klassen
  - Queue-Funktionalität: add, remove, insert, delete, clear
  - Navigation: next, previous, jump, index
  - Modi: shuffle, repeat (off/one/all)
- [x] **Streaming-Route:**
  - `web/routes/streaming.py` - FastAPI Route für `/stream.mp3`
  - Range-Request Support für Seeking
- [x] **Cometd/Bayeux Real-Time:** ✅
  - `web/cometd.py` - Long-Polling für iPeng, Squeezer, etc.
  - Ersetzt WebSocket für LMS-Kompatibilität
- [x] **UI (Web):** Svelte 5 + Tailwind v4 ✅
  - `web-ui/` - Modernes SPA Frontend
  - Cover Art mit BlurHash Placeholders
  - Adaptive Akzentfarben (node-vibrant)
  - Quality Badges, Sidebar Navigation
- [x] **Transcoding:** ✅
  - `streaming/transcoder.py` - faad→mp3 Pipeline für M4B/M4A/MP4
  - `streaming/policy.py` - Format-Entscheidungen

### Nächste Schritte:
- [ ] View Transitions API (CSS)
- [ ] Fullscreen Now Playing (3-Level UI)
- [ ] Virtual Scrolling (TanStack Virtual)

---

## 📚 Weiterführende Dokumentation

- [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md) - Projekt-Kontext und Session-Infos
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Allgemeine System-Architektur
- [SLIMPROTO.md](./SLIMPROTO.md) - Slimproto-Protokoll Details
- [E2E_TEST_GUIDE.md](./E2E_TEST_GUIDE.md) - End-to-End Test Anleitung

---

*Aktualisiert: Februar 2026 (Session 28 - Cover Art & API Fixes)*