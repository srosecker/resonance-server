# 🎵 Resonance — Architektur & Technische Referenz

SlimServer (Logitech Media Server) → Python Portierung

---

## 📋 Inhaltsverzeichnis

1. [Überblick](#1-überblick)
2. [Original-Architektur (Perl)](#2-original-architektur-perl)
3. [Ziel-Architektur (Python)](#3-ziel-architektur-python)
4. [Slimproto-Protokoll](#4-slimproto-protokoll)
5. [Audio-Streaming](#5-audio-streaming)
6. [Transcoding-Pipeline](#6-transcoding-pipeline)
7. [Musikbibliothek](#7-musikbibliothek)
8. [Multi-Room Sync](#8-multi-room-sync)
9. [CLI-Protokoll](#9-cli-protokoll)
10. [Web-Interface](#10-web-interface)
11. [Plugin-System](#11-plugin-system)
12. [Technologie-Stack](#12-technologie-stack)
13. [Projektstruktur](#13-projektstruktur)

---

## 1. Überblick

**Resonance** ist eine Python-Neuimplementierung des Logitech Media Server (LMS/SlimServer).

### Ziele
- Volle Kompatibilität mit Squeezebox-Hardware und Software-Playern (Squeezelite)
- Moderner, wartbarer Code
- Nutzung des Python-Ökosystems
- Einfache Erweiterbarkeit

### Nicht-Ziele (vorerst)
- 100% Feature-Parität von Tag 1
- Eigene Player-Implementierung

---

## 2. Original-Architektur (Perl)

### Kernmodule im Original

```
Slim/
├── Networking/
│   ├── Slimproto.pm      # Haupt-Protokoll (Port 3483)
│   ├── Discovery.pm      # Player-Discovery (UDP Broadcast)
│   └── Async.pm          # Event-Loop
├── Player/
│   ├── Client.pm         # Player-Abstraktion
│   ├── Player.pm         # Basis-Player-Logik
│   ├── Squeezebox.pm     # Hardware-spezifisch
│   ├── Song.pm           # Track-Handling
│   ├── Playlist.pm       # Playlist-Management
│   ├── Pipeline.pm       # Audio-Streaming
│   ├── Sync.pm           # Multi-Room
│   └── TranscodingHelper.pm
├── Music/                # Bibliotheks-Verwaltung
├── Schema/               # Datenbank
├── Web/                  # HTTP-Server & UI
└── Plugin/               # 48+ Plugins
```

### Warum Perl funktioniert

Der Server ist **nicht** performance-kritisch, weil:
1. **Audio-Verarbeitung** → Externe C-Binaries (flac, sox, ffmpeg)
2. **Streaming** → Kernel-I/O, nicht Perl
3. **Protokoll-Handling** → Nur Bytes shufflen, simple Logik

---

## 3. Ziel-Architektur (Python)

```
resonance/
├── resonance/
│   ├── __init__.py
│   ├── server.py              # Haupteinstiegspunkt
│   ├── config.py              # Konfiguration
│   │
│   ├── protocol/              # Netzwerk-Protokolle
│   │   ├── slimproto.py       # Slimproto (Port 3483)
│   │   ├── messages.py        # Message-Typen
│   │   ├── discovery.py       # UDP Discovery
│   │   └── cli.py             # CLI-Protokoll (Port 9090)
│   │
│   ├── player/                # Player-Verwaltung
│   │   ├── client.py          # Player-Abstraktion
│   │   ├── playlist.py        # Playlist-Logik
│   │   ├── sync.py            # Multi-Room Sync
│   │   └── types.py           # Device-Typen
│   │
│   ├── streaming/             # Audio-Streaming
│   │   ├── pipeline.py        # Streaming-Pipeline
│   │   ├── transcoder.py      # Transcoding-Manager
│   │   └── http.py            # HTTP-Streaming
│   │
│   ├── library/               # Musikbibliothek
│   │   ├── scanner.py         # Verzeichnis-Scanner
│   │   ├── metadata.py        # Metadaten-Extraktion
│   │   └── database.py        # DB-Zugriff
│   │
│   ├── web/                   # Web-Interface
│   │   ├── api.py             # REST-API
│   │   └── static/            # Frontend-Assets
│   │
│   └── plugins/               # Plugin-System
│       └── base.py            # Plugin-Basisklasse
│
├── tests/
├── docs/
├── pyproject.toml
└── README.md
```

---

## 4. Slimproto-Protokoll

### Übersicht

- **Port:** 3483 (TCP)
- **Binärprotokoll** mit 4-Byte Message-Tags
- **Bidirektional:** Server ↔ Player

### Message-Format

```
┌──────────────┬──────────────┬─────────────────┐
│ Tag (4 Byte) │ Länge (vary) │ Payload (vary)  │
└──────────────┴──────────────┴─────────────────┘
```

### Wichtige Messages (Client → Server)

| Tag | Name | Beschreibung |
|-----|------|--------------|
| `HELO` | Hello | Initiale Verbindung, Device-Info |
| `STAT` | Status | Heartbeat, Playback-Status |
| `IR  ` | Infrared | Fernbedienungs-Codes |
| `BYE!` | Goodbye | Verbindung trennen |
| `RESP` | Response | HTTP-Response-Header |
| `META` | Metadata | Stream-Metadaten |
| `DSCO` | Disconnect | Stream disconnected |
| `BUTN` | Button | Hardware-Buttons |
| `KNOB` | Knob | Drehregler |

### Wichtige Messages (Server → Client)

| Tag | Name | Beschreibung |
|-----|------|--------------|
| `strm` | Stream | Streaming-Befehle |
| `aude` | Audio Enable | Audio an/aus |
| `audg` | Audio Gain | Lautstärke |
| `setd` | Set Data | Konfiguration setzen |
| `grfb` | Graphics FB | Display-Update |

### HELO-Payload (Beispiel)

```
Byte  0:    Device ID
Bytes 1-2:  Revision
Bytes 3-8:  MAC-Adresse
Bytes 9-10: UUID-Länge
Bytes 11+:  UUID, Capabilities...
```

### Python-Implementierung (Konzept)

```python
import asyncio
import struct

SLIMPROTO_PORT = 3483

class SlimprotoServer:
    def __init__(self):
        self.clients: dict[str, PlayerClient] = {}
    
    async def start(self):
        server = await asyncio.start_server(
            self.handle_connection,
            host='0.0.0.0',
            port=SLIMPROTO_PORT
        )
        await server.serve_forever()
    
    async def handle_connection(self, reader, writer):
        while True:
            # 4-Byte Tag lesen
            tag = await reader.read(4)
            if not tag:
                break
            
            tag_str = tag.decode('ascii')
            handler = self.message_handlers.get(tag_str)
            if handler:
                await handler(reader, writer)
    
    message_handlers = {
        'HELO': handle_helo,
        'STAT': handle_stat,
        'BYE!': handle_bye,
        # ...
    }
```

---

## 5. Audio-Streaming

### Streaming-Modelle

1. **Direct Streaming** — Player holt Daten direkt vom Server
2. **Proxy Streaming** — Server leitet externe Streams weiter

### HTTP-Streaming

```
Player ──GET /stream.mp3──► Server
       ◄─────Audio-Daten────
```

Der Server teilt dem Player per `strm`-Message mit, welche URL er abrufen soll.

---

## 6. Transcoding-Pipeline

### Prinzip

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Quell-  │───►│ Decoder │───►│ Encoder │───► Player
│ Datei   │    │ (flac)  │    │ (sox)   │
└─────────┘    └─────────┘    └─────────┘
```

### convert.conf Format

```
# Format: source dest device_type device_id
# Nächste Zeile: Kommando

flac mp3 * *
    [flac] -dcs $FILE$ | [lame] -b $BITRATE$ - -

mp3 mp3 * *
    -
```

### Python-Konzept

```python
async def transcode(input_path: str, output_format: str):
    # FLAC → PCM
    decoder = await asyncio.create_subprocess_exec(
        'flac', '-d', '-c', input_path,
        stdout=asyncio.subprocess.PIPE
    )
    
    # PCM → MP3
    encoder = await asyncio.create_subprocess_exec(
        'lame', '-b', '320', '-', '-',
        stdin=decoder.stdout,
        stdout=asyncio.subprocess.PIPE
    )
    
    return encoder.stdout
```

---

## 7. Musikbibliothek

### Datenbank-Schema (Konzept)

```sql
CREATE TABLE tracks (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE,          -- file://path oder http://...
    title TEXT,
    artist_id INTEGER,
    album_id INTEGER,
    duration_ms INTEGER,
    bitrate INTEGER,
    samplerate INTEGER,
    channels INTEGER,
    filesize INTEGER,
    mtime INTEGER,            -- Modification time
    FOREIGN KEY (artist_id) REFERENCES artists(id),
    FOREIGN KEY (album_id) REFERENCES albums(id)
);

CREATE TABLE artists (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);

CREATE TABLE albums (
    id INTEGER PRIMARY KEY,
    title TEXT,
    artist_id INTEGER,
    year INTEGER,
    artwork_url TEXT
);

CREATE TABLE playlists (
    id INTEGER PRIMARY KEY,
    name TEXT,
    client_id TEXT            -- NULL = Server-Playlist
);

CREATE TABLE playlist_tracks (
    playlist_id INTEGER,
    track_id INTEGER,
    position INTEGER,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id),
    FOREIGN KEY (track_id) REFERENCES tracks(id)
);
```

### Scanner

```python
from pathlib import Path
import mutagen

async def scan_directory(root: Path):
    for path in root.rglob('*'):
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            metadata = mutagen.File(path)
            await add_or_update_track(path, metadata)
```

---

## 8. Multi-Room Sync

### Herausforderung

Mehrere Player sollen sample-genau synchron spielen.

### Prinzip (aus Original)

1. Server sendet Timestamp mit jedem Audio-Chunk
2. Player puffern und spielen zeitversetzt ab
3. Regelmäßiger Sync-Check über STAT-Messages
4. Latenz-Kompensation pro Player

### Relevante Dateien im Original

- `Slim/Player/Sync.pm`
- `Slim/Player/SongStreamController.pm`

---

## 9. CLI-Protokoll

### Übersicht

- **Port:** 9090 (TCP/Telnet)
- **Textbasiert:** Befehle und Antworten als Strings
- **Zeilenorientiert:** Ein Befehl pro Zeile

### Befehlsformat

```
<playerid> <command> <args...>
```

### Beispiele

```
# Pause-Toggle für Player
00:04:20:12:34:56 pause

# Lautstärke abfragen
00:04:20:12:34:56 mixer volume ?

# Titel abspielen
00:04:20:12:34:56 playlist play /music/song.flac
```

---

## 10. Web-Interface

### Original

- Template-basiert (Template Toolkit)
- AJAX für dynamische Updates
- Skins für verschiedene Geräte

### Resonance (geplant)

- FastAPI Backend
- REST-API für alle Operationen
- Modernes Frontend (Vue/React/Svelte TBD)
- Server-Sent Events für Live-Updates

---

## 11. Plugin-System

### Original

48+ Plugins für:
- Streaming-Dienste (Spotify, Deezer via 3rd-Party)
- Internet-Radio
- Podcasts
- Spiele (SlimTris!)
- Visualisierungen

### Resonance (Konzept)

```python
from abc import ABC, abstractmethod

class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    async def on_load(self, server):
        pass
    
    async def on_unload(self):
        pass
```

---

## 12. Technologie-Stack

| Komponente | Technologie | Begründung |
|------------|-------------|------------|
| Async Runtime | asyncio | Standard, gut unterstützt |
| Web Framework | FastAPI | Modern, schnell, OpenAPI |
| Datenbank | SQLite + aiosqlite | Einfach, serverless |
| Audio-Metadaten | mutagen | Standard für Python |
| Transcoding | ffmpeg, flac, sox | Bewährt, wie im Original |
| Config | TOML | Modern, lesbar |
| Logging | Python logging | Standard |
| Testing | pytest | Standard |

---

## 13. Projektstruktur

```
resonance/
├── resonance/           # Hauptpaket
│   ├── __init__.py
│   ├── __main__.py      # Entry: python -m resonance
│   └── ...
├── tests/               # Tests
├── docs/                # Dokumentation
│   ├── AI_BOOTSTRAP.md
│   ├── ARCHITECTURE.md  # (diese Datei)
│   ├── CHANGELOG.md
│   └── TODO.md
├── bin/                 # Native Binaries (optional)
├── pyproject.toml       # Projekt-Konfiguration
├── README.md
└── LICENSE
```

---

## 📚 Verwandte Dokumente

- [TODO.md](./TODO.md) - Aufgabenliste & Roadmap
- [CHANGELOG.md](./CHANGELOG.md) - Änderungshistorie
- [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md) - Kontext für AI-Assistenten

---

*Zuletzt aktualisiert: Februar 2026*

> **Hinweis:** Diese Datei beschreibt die grundlegende Architektur. Für den aktuellen Implementierungsstatus siehe [ARCHITECTURE_WEB.md](./ARCHITECTURE_WEB.md) und [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md).