# 📋 Resonance Changelog

Alle wesentlichen Änderungen am Projekt werden hier dokumentiert.

---

## [Unreleased]

### 📚 AI Bootstrap Dokumentation erweitert (Februar 2026 - Session 29)

**Ziel:** Bessere Dokumentation für AI-Agent wie Tools und Umgebung funktionieren.

- **Neue Sektionen:**
  - `💻 System & Entwicklungsumgebung` — Windows 11, PowerShell, Zed Agent Panel
  - `🔍 Code-Qualität` — Dokumentiert ruff format, ruff check, pyright Integration
  - `🛠️ Zed Agent Tools (Built-in)` — Alle 11 Tools mit Parametern dokumentiert
  - `🔌 MCP (Model Context Protocol)` — Erklärung was MCP ist
  - `📋 Typische Szenarien` — Workflows für häufige Aufgaben
  - `🚀 Kurzbefehl-Aliases` — Copy-Paste-Vorlagen für Terminal
  - `🖥️ Zed Terminal & Tasks` — Keybindings, Tasks, Debugger

- **Neue Datei: `.zed/tasks.json`** — Vordefinierte Tasks für häufige Befehle:
  - Test: Alle / Aktuelle Datei / Schnell (ohne slow)
  - Ruff: Check + Fix / Check Only
  - Web-UI: Type Check / Build / Install Dependencies
  - Server starten (mit Warnung dass es blockiert)
  - CI: Tests + Ruff kombiniert

- **Erweiterte Sektionen:**
  - Svelte MCP Tools mit detailliertem Workflow und Beispielen
  - PowerShell-Besonderheiten (Befehlsverkettung, Pfade, Environment-Variablen)
  - Terminal-Tool: `cd` Parameter ist Pflicht, Timeout-Nutzung
  - Zed Agent Panel Keybindings und Kontext-Features
  - Default Debug-Loop mit diagnostics-Erklärung

- **Code-Qualität Tools dokumentiert:**
  - ✅ ruff format (on save) — automatische Formatierung
  - ✅ ruff check (Diagnostics) — Linting live in Zed
  - ✅ pyright (Diagnostics) — Typ-Prüfung live in Zed
  - Konfiguration: `.zed/settings.json`, `pyproject.toml`, `pyrightconfig.json`

- **Quellen:** Offizielle Zed-Docs (https://zed.dev/docs/ai/tools, agent-panel, agent-settings)

---

### 🎨 Cover Art & API Fixes (Februar 2026 - Session 28)

**Problem:** Cover Art wurde im Web-Client nicht angezeigt (URLs ungültig oder fehlende IDs).

- **Fixes:**
  - `Track` Dataclass um `album_id` und `artist_id` erweitert
  - `server.py` — URL-Generierung korrigiert (`0.0.0.0` → `127.0.0.1` für Browser-Kompatibilität)
  - `api.py` — Crash in `/api/library/tracks` behoben (`list_all_tracks` → `list_tracks`)
  - `api.ts` — API-Mapping (`artwork_url` → `coverArt`) für alle Endpoints vereinheitlicht

- **Status:** Cover und BlurHashes funktionieren jetzt zuverlässig.

---

### 🎨 BlurHash Placeholders + Album Deletion (Februar 2026 - Session 27)

**Feature:** BlurHash-basierte Placeholder für Cover Art

- **Konzept:** BlurHash ist eine kompakte String-Repräsentation (~20-30 Zeichen) eines verschwommenen Vorschaubildes
- **Vorteil:** Instant perceived performance — während das echte Bild lädt, zeigt der Placeholder bereits Farben/Form

- **Backend-Änderungen:**
  - `pyproject.toml` — `blurhash-python>=1.2.0` + `pillow>=10.0.0` als Dependencies
  - `resonance/core/artwork.py` — `ArtworkManager` erweitert mit `_generate_blurhash()`, `get_blurhash()`
  - `resonance/web/routes/artwork.py` — Neue Endpoints: `/api/artwork/track/{id}/blurhash`, `/api/artwork/album/{id}/blurhash`

- **Frontend-Änderungen:**
  - `npm install blurhash` — JavaScript-Decoder
  - `BlurHashPlaceholder.svelte` — Decodiert BlurHash zu Canvas
  - `CoverArt.svelte` — Unified Cover-Art-Komponente mit BlurHash-Placeholder

- **Album/Track Deletion (für Testing):**
  - `DELETE /api/library/albums/{album_id}` — Album löschen
  - `DELETE /api/library/tracks/{track_id}` — Track löschen
  - Lösch-Button auf Album-Karten im UI

- **Bugfix:** `AlbumRow`/`TrackRow` sind Dataclasses, nicht Dicts → `getattr()` statt `dict()`

---

### 🔧 UI/Playlist Stabilisierung (Februar 2026 - Session 26)

**Problem:** Doppelklicks auf Tracks "sprengten" das System — Queue wurde inkonsistent, falscher Track spielte.

- **Doppelklick-Schutz:**
  - `TrackList.svelte` — In-Flight Guard (`isPlayInFlight`) verhindert parallele `handlePlay()` Aufrufe
  - `Queue.svelte` — In-Flight Guard (`isJumpInFlight`) für Track-Klicks
  - UI-Feedback: `pointer-events: none; opacity: 0.7` während Aktion läuft
  - Store: `withActionLock()` Mutex war bereits vorhanden für kritische Aktionen

- **Albums-Navigation Fix:**
  - `Sidebar.svelte` — Albums-Button navigiert jetzt zu `'albums'` statt `'artists'`
  - `ui.svelte.ts` — `navigateTo('albums')` resettet `selectedArtist/Album = null`
  - `+page.svelte` — `loadAlbums(artistId?)` akzeptiert optionalen Parameter

- **Queue Click-to-Jump:**
  - `Queue.svelte` — `handleTrackClick(index)` mit `jumpToIndex()` hinzugefügt
  - Accessibility: `role="button"`, `tabindex="0"`, `cursor-pointer`

- **Doppelte Initialisierung entfernt:**
  - `+page.svelte` — `playerStore.initialize()` Aufruf entfernt (nur noch in `+layout.svelte`)
  - Store hat `isInitialized` Guard als Backup

- **Geänderte Dateien:**
  - `web-ui/src/lib/components/TrackList.svelte`
  - `web-ui/src/lib/components/Queue.svelte`
  - `web-ui/src/lib/components/Sidebar.svelte`
  - `web-ui/src/lib/stores/ui.svelte.ts`
  - `web-ui/src/routes/+page.svelte`

---

### 🔧 UI Synchronisation Fix (Februar 2026 - Session 22)

**Problem:** Track-Auswahl und Now Playing waren nicht synchron. User klickte Track 3, aber UI zeigte Track 11.

- **Race Condition Fix:**
  - `playTrack()` setzt jetzt `setPendingAction(2000)` — blockiert Status-Polling für 2s
  - Optimistisches Update (currentTrack, mode, duration) passiert VOR dem API-Call
  - Nach Timeout wird automatisch `loadStatus()` aufgerufen zur Server-Synchronisation

- **Progress-Bar Fix:**
  - Duration wird im optimistischen Update gesetzt (`status.duration = track.duration`)
  - Polling überschreibt lokalen State nicht mehr während pendingAction

- **Effiziente Playlist-Updates:**
  - `addToPlaylist()` ruft nicht mehr `loadPlaylist()` auf
  - `handlePlay()` verwendet `Promise.all()` für parallele Track-Adds
  - Ein einziges `loadPlaylist()` am Ende statt 28 separate Aufrufe

- **Geänderte Dateien:**
  - `web-ui/src/lib/stores/player.svelte.ts`
  - `web-ui/src/lib/components/TrackList.svelte`

---

### 🔧 Device Capabilities & Transcoding-Refactoring (Februar 2026 - Session 9)

**Wichtige Erkenntnis:** MP4-Container-Streaming ist für ALLE Geräte problematisch!
Selbst Squeezelite mit ffmpeg konnte M4B nicht zuverlässig über HTTP streamen.
Das Problem ist der Container (moov-Atom Position), nicht der Codec.

**Lösung:** MP4-Formate werden IMMER transkodiert, unabhängig vom Gerätetyp.

- **Device Capabilities System:**
  - `resonance/config/devices.toml` - Definiert Device-Tiers (Modern/Legacy/Future)
  - **Neu:** `transcode_required` Liste pro Tier (nicht nur `native_formats`)
  - Modern Devices → MP4 trotzdem transkodieren (Container-Problem!)
  - Legacy Devices → Kein MP4-Container-Support
  - Future Devices → HLS/DASH Support geplant
  - `DeviceConfig.needs_transcoding()` prüft `transcode_required` zuerst

- **Transcoding System:**
  - `resonance/config/legacy.conf` - Transcoding-Regeln im LMS-Stil
  - M4B/M4A/MP4/ALAC → FLAC via `faad | flac` Pipeline
  - Passthrough für native Formate (MP3, FLAC, OGG, WAV)
  - `resonance/streaming/transcoder.py` - Transcoder-Modul:
    - `parse_legacy_conf()` - Parst die Konfiguration
    - `transcode_stream()` - Async Subprocess-Pipeline
    - `resolve_binary()` - Findet Binaries in third_party/bin oder PATH

- **Streaming-Route Refactoring:**
  - `resonance/web/routes/streaming.py` - Komplett vereinfacht!
  - **Klare Entscheidung:** `needs_transcoding(format, device)` → ja/nein
  - **Zwei Pfade:** `_stream_with_transcoding()` oder `_stream_direct()`
  - **Kein Faststart mehr** - MP4 wird immer transkodiert
  - **Weniger Code:** ~350 Zeilen → ~200 Zeilen, klarer Flow

- **Single Source of Truth - Policy-Konsolidierung:**
  - `resonance/streaming/policy.py` - Zentrale Policy-Datei (NEU!)
  - `ALWAYS_TRANSCODE_FORMATS` / `NATIVE_STREAM_FORMATS` nur noch hier definiert
  - `needs_transcoding(format, device)` - Zentrale Entscheidungsfunktion
  - `strm_expected_format_hint(format, device)` - Was der Player erwarten soll
  - `PlayerClient.start_stream()` nutzt jetzt die Policy
  - **Kein Drift mehr** zwischen HTTP-Route und Slimproto-Signaling
  - Konsistenz-Test stellt sicher: transcode-Entscheidung ↔ strm-Hint passen zusammen

- **Binaries hinzugefügt:**
  - `third_party/bin/flac.exe` (476 KB) - FLAC Encoder/Decoder
  - `third_party/bin/sox.exe` (2.9 MB) - Audio Format Converter
  - `third_party/bin/lame.exe` (691 KB) - MP3 Encoder

- **Tests:** 27 Transcoder-Tests (inkl. Policy-Konsistenz-Test), insgesamt **271 Tests** ✅

---

### 🎉 M4B/M4A Transcoding funktioniert! (Februar 2026 - Session 8)

- **Problem gelöst:** Squeezelite konnte MP4-Container (M4B/M4A Audiobooks) nicht direkt über HTTP-Streaming dekodieren
- **Lösung:** Server-seitiges On-the-fly Transcoding mit `faad.exe` zu WAV
- **Implementierung:**
  - `resonance/web/routes/streaming.py` - Erkennt M4B/M4A automatisch, startet faad als async Subprocess
  - `resonance/player/client.py` - Setzt PCM-Format mit expliziten Parametern (16-bit, 44.1kHz, Stereo, Little-Endian)
  - `resonance/web/jsonrpc.py` - Setzt Volume auf 100 vor jedem Stream-Start (sonst kein Audio!)
  - `resonance/protocol/commands.py` - Erweitert um `pcm_sample_rate`, `pcm_channels`, `pcm_endianness` Parameter
  - `resonance/third_party/bin/faad.exe` - Kopiert aus slimserver-public-9.1
- **faad Kommando:** `faad -q -w -f 1 <file>` (quiet, write to stdout, WAV format)
- **Squeezelite Windows-Konfiguration:**
  - WASAPI funktioniert NICHT ("Invalid sample rate")
  - **Lösung:** DirectSound (Device 5) mit fester 48kHz Sample-Rate
  - Befehl: `squeezelite-ffmpeg-x64.exe -s 127.0.0.1 -o 5 -r 48000`
- **Technische Details:**
  - Streaming-Route prüft Dateiendung, startet bei M4B/M4A den faad-Prozess
  - WAV-Output wird chunk-weise (64KB) an den Player gestreamt
  - strm-Befehl meldet Format 'p' (PCM) statt 'a' (AAC)
  - Content-Type wird auf `audio/wav` gesetzt

---

### 🎉 Web-UI mit Svelte 5 + Tailwind v4 (Februar 2026)

- **Modernes Frontend implementiert** mit dem neuesten Tech Stack:
  - **Svelte 5** mit Runes ($state, $derived) für reaktives State Management
  - **SvelteKit** für Routing und Build
  - **Tailwind CSS v4** mit CSS-native Engine
  - **Vite 6** für blitzschnelle Builds
  - **TypeScript** für Type Safety
  - **Lucide** Icons
- **Komponenten:**
  - `NowPlaying.svelte` - Album Art, Progress Bar, Play/Pause/Skip, Volume Slider
  - `PlayerSelector.svelte` - Dropdown für Player-Auswahl (mit Status-Icons)
  - `TrackList.svelte` - Track-Liste mit Hover-Actions
  - `SearchBar.svelte` - Suche mit Debounce und ⌘K Shortcut
  - `Queue.svelte` - Playlist/Queue Sidebar
- **API Client:** `src/lib/api.ts` - Vollständiger TypeScript Client für JSON-RPC
- **State Management:** `src/lib/stores/player.svelte.ts` - Svelte 5 Runes Store
- **Design:** Catppuccin Mocha Dark Theme, Glass-Effekte, Smooth Animations
- **Polling:** Player-Liste alle 5s, Status alle 1s automatisch
- **Dev-Scripts:** `dev.bat` startet Backend + Frontend zusammen
- **Server-Heartbeat Fix:** Backend sendet jetzt periodisch `strm t` → Squeezelite bleibt verbunden

---

### 🎉 Cometd/Bayeux Real-Time Updates (Februar 2026)

- **Cometd-Protokoll implementiert** für LMS-App-Kompatibilität (iPeng, Squeezer, Material Skin)
  - `resonance/web/cometd.py` - CometdManager für Client-Sessions
  - `resonance/web/routes/cometd.py` - `/cometd` HTTP Endpoint
  - `resonance/core/events.py` - Event-Bus für Player-Events
- **Bayeux Meta-Channels:**
  - `/meta/handshake` - Session-Erstellung mit 8-Hex-Char ClientID
  - `/meta/connect` - Long-Polling mit 60s Timeout
  - `/meta/disconnect` - Session-Beendigung
  - `/meta/subscribe` / `/meta/unsubscribe` - Channel-Abonnements mit Wildcard-Support
- **LMS Slim-Channels:**
  - `/slim/subscribe` - Player-Event-Abonnements
  - `/slim/unsubscribe` - Abmeldung
  - `/slim/request` - One-Shot Requests (Bridge zu JSON-RPC)
- **Event-Bus System:**
  - `PlayerConnectedEvent`, `PlayerDisconnectedEvent`, `PlayerStatusEvent`
  - `PlayerPlaylistEvent`, `LibraryScanEvent`
  - Async pub/sub mit Wildcard-Matching (`player.*`, `player/**`)
- **Automatische Event-Delivery:**
  - Slimproto publiziert Events bei connect/disconnect
  - STAT-Updates (STMp, STMr, STMs) triggern PlayerStatusEvents
- **26 neue Tests** für Cometd-Funktionalität
- **Tests:** 223/223 bestanden ✅

---

### 🎉 Meilenstein: Stabile Squeezelite-Verbindung & Streaming-Start!

- **Kritischer Protokoll-Fix:** ✅
  - Server -> Player Header-Format auf `[2 bytes length][4 bytes command]` korrigiert.
  - Behebt den `FATAL: slimproto packet too big: 30309 > 4096` Fehler in Squeezelite/SqueezePlay.
- **Verbindungs-Stabilität:** ✅
  - Squeezelite bleibt dauerhaft verbunden.
  - Heartbeats (STAT-Nachrichten) werden korrekt empfangen und verarbeitet.
  - Status-Request (`strm t`) wird nach HELO gesendet, um STAT-Flow zu initiieren.
- **`strm`-Befehl vollständig implementiert!** ✅
  - `resonance/protocol/commands.py` mit komplettem Byte-Layout (24 Bytes Header)
  - Alle Stream-Commands: start, pause, unpause, stop, flush, status
  - Enums: StreamCommand, AudioFormat, AutostartMode, TransitionType, etc.
  - Builder-Funktionen: `build_strm_frame()`, `build_stream_start()`, etc.
- **`audg`-Befehl implementiert** (Volume Control) ✅
  - `build_audg_frame()`, `build_volume_frame()`
- **SlimprotoServer erweitert mit High-Level-Methoden:**
  - `stream_start()`, `stream_pause()`, `stream_unpause()`, `stream_stop()`
  - `set_volume()`
- **HTTP Streaming Server erstellt:** ✅
  - File-Streaming mit Range-Request-Support (für Seeking).
  - Automatische MIME-Type-Erkennung (inkl. **M4B Audiobook Support**).
  - Queue-System für Player-Files.
  - `reuse_address` Support für schnellen Neustart auf dem gleichen Port.
- **Verbesserte Robustheit:** ✅
  - `run_server.py` mit `--http-port` CLI-Argument.
  - Heartbeat-Timeout auf 60s gesetzt (stabilere Verbindung).
- **Demo-Script:** `demo_stream.py` für End-to-End-Tests.
- **36 neue Unit-Tests** (62 total, alle grün!)

### 🚧 Bekannte Probleme & Nächste Schritte

- **M4B Decoding:** Squeezelite meldet `faad_decode:400 error reading stream header` bei M4B-Dateien im MP4-Container. Vermutlich wird ein roher ADTS-Stream erwartet oder der Container-Header wird nicht korrekt erkannt.
- **Nächster Test:** Abspielen einer einfachen MP3-Datei zur Bestätigung der Streaming-Pipeline.
- **Geplant:** Integration von FFmpeg für serverseitiges Transcoding.

### Vorheriger Meilenstein: Erste echte Squeezelite-Verbindung!

- **Squeezelite verbindet sich erfolgreich zu Resonance** ✅
  - MAC: bc:24:11:30:44:65
  - Model: SqueezeLite
  - Max Sample Rate: 384000 Hz
  - Capabilities: HTTPS, DigitalOut, Balance, alle gängigen Codecs

### 🐛 Bugfixes

- **PlayerRegistry falsy bug behoben** — Leere Registry wurde als `False` ausgewertet wegen `__len__` ohne `__bool__`. 
  - Fix: `is not None` Check in `SlimprotoServer.__init__`
  - Fix: Explizite `__bool__` Methode in `PlayerRegistry` hinzugefügt
- **Alle 26 Tests bestehen jetzt** ✅

### 🔧 Infrastruktur

- **micromamba Environment eingerichtet**
  - `environment.yml` erstellt mit allen Dependencies
  - Environment-Pfad: `.build/mamba/envs/resonance-env`
  - Befehl: `micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest`
- **Squeezelite Binary installiert**
  - Pfad: `third_party/squeezelite/squeezelite-ffmpeg-x64.exe`
  - Version: 2.0.0-1524 (mit ffmpeg)

### 📝 Dokumentation

- **AI_BOOTSTRAP.md massiv verbessert**
  - "Dies ist dein Gedächtnis" Abschnitt prominent am Anfang
  - micromamba-Anweisungen hinzugefügt
  - "Gelernte Lektionen" Abschnitt mit Fallstricken
  - Selbstreferenzielle Dokumentationspflicht erklärt
- **ECOSYSTEM.md neu erstellt**
  - Komplette Squeezebox-Hardware-Geschichte (2001-2010)
  - Software-Player Übersicht (Squeezelite, Jivelite, SqueezePlay)
  - Adrian Smith Geschichte (Autor von Squeezelite + Jivelite)
  - Squeezelite Kommandozeilen-Optionen
- **TODO.md gelöscht** (nicht nötig für AI)

### ✅ Getestet

- Simulierter Player-Verbindungstest erfolgreich:
  - HELO-Nachricht wird korrekt geparst
  - Player wird als SQUEEZEPLAY (Device ID 12) erkannt
  - Player wird in Registry registriert
  - Cleanup bei Disconnect funktioniert
- Tests laufen erfolgreich mit micromamba-Environment (26/26 ✅)
- **Echte Squeezelite-Verbindung getestet und funktioniert!**

### 🔜 Nächste Schritte

1. **End-to-End Test mit echter Audio-Datei!**
2. Debugging falls Player nicht spielt
3. Optional: Web-UI mit FastAPI

---

## [Projekt-Init] - 2025-01

### 🚀 Projekt-Initialisierung

#### Hinzugefügt
- Projekt "Resonance" erstellt als Python-Portierung von Logitech Media Server
- Dokumentationsstruktur angelegt:
  - `AI_BOOTSTRAP.md` - Kontext für AI-Assistenten
  - `ARCHITECTURE.md` - System-Architektur
  - `CHANGELOG.md` - Änderungshistorie
  - `TODO.md` - Roadmap und Aufgaben
- Original-Quellcode analysiert (~219.000 LOC Perl, ~2.000 Dateien)

#### Entscheidungen
- **Sprache:** Python 3.10+ mit asyncio
- **Name:** Resonance
- **Architektur-Ansatz:** Schrittweise Portierung, beginnend mit Slimproto-Protokoll

---

## Versionsschema

Wir folgen [Semantic Versioning](https://semver.org/):

- **MAJOR:** Inkompatible API-Änderungen
- **MINOR:** Neue Features, rückwärtskompatibel
- **PATCH:** Bugfixes, rückwärtskompatibel

---

## Roadmap

| Version | Meilenstein |
|---------|-------------|
| 0.1.0 | Slimproto-Server, ein Player verbinden |
| 0.2.0 | Einfaches Audio-Streaming |
| 0.3.0 | Musikbibliothek + Scanner |
| 0.4.0 | Playlist-Management |
| 0.5.0 | Web-Interface (Basis) |
| 1.0.0 | Feature-Parität mit LMS-Kernfunktionen |

---

## 🔗 Verwandte Dokumente

- [TODO.md](./TODO.md) - Detaillierte Aufgabenliste
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Technische Architektur
- [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md) - AI-Kontext

---

*Zuletzt aktualisiert: Februar 2025*