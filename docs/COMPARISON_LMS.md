# 🔄 Feature-Vergleich: LMS (SlimServer) vs Resonance

Dieser Vergleich zeigt den aktuellen Implementierungsstand von Resonance gegenüber dem Original Logitech Media Server (LMS/Lyrion).

---

## 📊 Übersicht

| Kategorie | LMS (Perl) | Resonance (Python) |
|-----------|------------|-------------------|
| **Codebase** | ~200k+ LOC | ~16.200 LOC |
| **Sprache** | Perl 5 | Python 3.11+ |
| **Alter** | 2001-heute (24 Jahre) | 2025-heute |
| **Plugins** | 48+ eingebaut | 0 (noch kein Plugin-System) |

---

## 🎯 Kern-Funktionen

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **Slimproto Server (Port 3483)** | ✅ | ✅ | Vollständig |
| **HTTP Streaming (Port 9000)** | ✅ | ✅ | Vollständig |
| **Player-Erkennung (HELO)** | ✅ | ✅ | Vollständig |
| **Player-Status (STAT)** | ✅ | ✅ | Vollständig |
| **Stream-Kontrolle (strm)** | ✅ | ✅ | Vollständig |
| **Volume-Kontrolle (audg)** | ✅ | ✅ | Vollständig |
| **Audio Enable (aude)** | ✅ | 📋 | Stub |
| **Display-Befehle (grfe/grfb)** | ✅ | 📋 | Stub (nicht relevant für Squeezelite) |
| **IR-Fernbedienung** | ✅ | 📋 | Stub |
| **UDP Discovery** | ✅ | ❌ | Nicht implementiert |

---

## 🎵 Audio & Streaming

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **MP3 Direct Streaming** | ✅ | ✅ | Vollständig |
| **FLAC Direct Streaming** | ✅ | ✅ | Vollständig |
| **OGG/Vorbis Streaming** | ✅ | ✅ | Vollständig |
| **AAC/M4A Transcoding** | ✅ | ✅ | Via faad→mp3 |
| **M4B (Audiobooks) Transcoding** | ✅ | ✅ | Via faad→mp3 |
| **ALAC (Apple Lossless)** | ✅ | ❌ | Nicht implementiert |
| **WMA Transcoding** | ✅ | ❌ | Nicht implementiert |
| **DSD/DoP** | ✅ | ❌ | Nicht implementiert |
| **Gapless Playback** | ✅ | ⚠️ | Teilweise (Player-abhängig) |
| **Crossfade** | ✅ | ❌ | Nicht implementiert |
| **Replay Gain** | ✅ | ❌ | Nicht implementiert |
| **Range Requests (Seeking)** | ✅ | ✅ | Vollständig |

---

## 📚 Musikbibliothek

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **Ordner-Scanning** | ✅ | ✅ | Vollständig |
| **Metadaten-Extraktion** | ✅ | ✅ | Via mutagen |
| **SQLite Datenbank** | ✅ | ✅ | Schema v8 |
| **Artists/Albums/Tracks** | ✅ | ✅ | Vollständig |
| **Genres** | ✅ | ✅ | Vollständig |
| **Contributors/Roles** | ✅ | ✅ | Composer, Conductor, etc. |
| **Compilation-Flag** | ✅ | ✅ | Vollständig |
| **Cover Art Extraktion** | ✅ | ✅ | ID3, MP4, FLAC, Vorbis |
| **BlurHash Placeholders** | ❌ | ✅ | Resonance-exklusiv! |
| **Inkrementeller Rescan** | ✅ | ⚠️ | Basis (mtime-basiert) |
| **Artwork Resizing** | ✅ | ❌ | Nicht implementiert |
| **Virtual Libraries** | ✅ | ❌ | Nicht implementiert |
| **Playlists (M3U, PLS)** | ✅ | ❌ | Nicht implementiert |
| **Volltext-Suche** | ✅ | ✅ | LIKE-basiert |
| **iTunes Import** | ✅ | ❌ | Nicht implementiert |
| **MusicIP/MusicMagic** | ✅ | ❌ | Nicht implementiert |

---

## 📋 Playlist & Playback

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **Queue (Now Playing)** | ✅ | ✅ | Vollständig |
| **Add/Remove/Clear** | ✅ | ✅ | Vollständig |
| **Play/Pause/Stop** | ✅ | ✅ | Vollständig |
| **Next/Previous** | ✅ | ✅ | Vollständig |
| **Jump to Track** | ✅ | ✅ | Vollständig |
| **Shuffle Mode** | ✅ | ✅ | Vollständig |
| **Repeat (Off/One/All)** | ✅ | ✅ | Vollständig |
| **Seek (Zeit-Position)** | ✅ | ✅ | Vollständig |
| **Save/Load Playlists** | ✅ | ❌ | Nicht implementiert |
| **Party Mode** | ✅ | ❌ | Nicht implementiert |
| **Sleep Timer** | ✅ | ❌ | Nicht implementiert |
| **Alarm/Wecker** | ✅ | ❌ | Nicht implementiert |

---

## 🔊 Multi-Room & Sync

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **Mehrere Player** | ✅ | ✅ | Vollständig |
| **Player-Registry** | ✅ | ✅ | Vollständig |
| **Sync-Gruppen** | ✅ | ❌ | Nicht implementiert |
| **Sample-genaue Sync** | ✅ | ❌ | Nicht implementiert |
| **Latenz-Kompensation** | ✅ | ❌ | Nicht implementiert |

---

## 🌐 Web-Interface & API

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **HTTP Server** | ✅ | ✅ | FastAPI |
| **JSON-RPC API** | ✅ | ✅ | LMS-kompatibel |
| **REST API** | ⚠️ | ✅ | Resonance erweitert |
| **Cometd/Bayeux (Long-Polling)** | ✅ | ✅ | Für iPeng, Squeezer |
| **CLI (Telnet, Port 9090)** | ✅ | ❌ | Nicht implementiert |
| **Web-UI (Default Skin)** | ✅ | ✅ | Svelte 5 + Tailwind |
| **Material Skin** | ✅ (Plugin) | ❌ | Nicht integriert |
| **Settings/Konfiguration** | ✅ | ❌ | Nicht implementiert |
| **CORS Support** | ⚠️ | ✅ | Vollständig |

---

## 📱 App-Kompatibilität

| App | LMS | Resonance | Status |
|-----|-----|-----------|--------|
| **iPeng (iOS)** | ✅ | ✅ | Getestet |
| **Squeezer (Android)** | ✅ | ✅ | Getestet |
| **Orange Squeeze** | ✅ | ⚠️ | Sollte funktionieren |
| **Material Skin (Web)** | ✅ | ⚠️ | Teilweise (kein Plugin-System) |

---

## 🎛️ Player-Unterstützung

| Player-Typ | LMS | Resonance | Status |
|------------|-----|-----------|--------|
| **Squeezelite** | ✅ | ✅ | Vollständig getestet |
| **Squeezebox Classic (SB3)** | ✅ | ⚠️ | Sollte funktionieren |
| **Squeezebox Touch** | ✅ | ⚠️ | Sollte funktionieren |
| **Squeezebox Radio** | ✅ | ⚠️ | Sollte funktionieren |
| **Transporter** | ✅ | ⚠️ | Sollte funktionieren |
| **Boom** | ✅ | ⚠️ | Sollte funktionieren |
| **SLIMP3** | ✅ | ❌ | Nicht unterstützt |
| **SoftSqueeze** | ✅ | ⚠️ | Ungetestet |
| **piCorePlayer** | ✅ | ⚠️ | Ungetestet |

---

## 🔌 Plugins & Erweiterungen

| Plugin-Kategorie | LMS | Resonance | Status |
|------------------|-----|-----------|--------|
| **Plugin-System** | ✅ (48+ Plugins) | ❌ | Nicht implementiert |
| **Spotify (via 3rd-Party)** | ✅ | ❌ | — |
| **Podcasts** | ✅ | ❌ | — |
| **Internet Radio** | ✅ | ❌ | — |
| **Last.fm Scrobbling** | ✅ | ❌ | — |
| **Favorites** | ✅ | ❌ | — |
| **Random Mix** | ✅ | ❌ | — |
| **Don't Stop The Music** | ✅ | ❌ | — |
| **UPnP/DLNA Bridge** | ✅ | ❌ | — |

---

## 🏗️ Infrastruktur

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **Konfigurationsdatei** | ✅ (server.prefs) | ⚠️ | Minimal (CLI-Argumente) |
| **Logging** | ✅ | ✅ | Python logging |
| **Systemd Service** | ✅ | ❌ | Nicht vorbereitet |
| **Docker Support** | ✅ | ❌ | Nicht vorbereitet |
| **Windows Service** | ✅ | ❌ | Nicht vorbereitet |
| **Automatische Updates** | ✅ | ❌ | — |

---

## ✨ Resonance-exklusive Features

Features, die Resonance hat, aber LMS nicht (oder schlechter):

| Feature | Beschreibung |
|---------|--------------|
| **BlurHash Placeholders** | Sofortige farbige Placeholder für Cover Art |
| **Adaptive Akzentfarben** | Automatische Farbextraktion aus Album-Art (node-vibrant) |
| **Modernes Frontend** | Svelte 5 + Tailwind v4 (vs. jQuery) |
| **Quality Badges** | Hi-Res Audio Kennzeichnung |
| **Async von Grund auf** | Python asyncio statt Perl-Event-Loop |

---

## 📈 Zusammenfassung

### ✅ Was Resonance gut kann (Phase 3 abgeschlossen)

- Squeezelite-Player vollständig steuern
- Musik scannen, indizieren, durchsuchen
- Streaming (MP3, FLAC, OGG, M4A/M4B)
- LMS-kompatible Apps (iPeng, Squeezer) bedienen
- Modernes Web-UI mit Cover Art

### ❌ Was noch fehlt

- **Multi-Room Sync** — Das Killer-Feature von LMS
- **Plugin-System** — Keine Erweiterbarkeit
- **Internet Radio / Podcasts** — Keine Streaming-Dienste
- **UDP Discovery** — Player müssen Server-IP kennen
- **Persistente Konfiguration** — Keine Settings-UI
- **CLI (Port 9090)** — Telnet-Interface fehlt

### 🎯 Empfohlene nächste Prioritäten

1. **UDP Discovery** — Damit Player den Server automatisch finden
2. **Sync-Gruppen** — Multi-Room ist DAS Squeezebox-Feature
3. **Persistente Playlists** — Save/Load von Playlists
4. **Konfigurationsdatei** — server.toml oder ähnlich

---

*Stand: Februar 2026 — Resonance v0.1.0*