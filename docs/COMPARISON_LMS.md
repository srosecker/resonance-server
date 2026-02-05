# 🔄 Feature-Vergleich: LMS vs Resonance

Aktueller Implementierungsstand von Resonance gegenüber dem Original Logitech Media Server (LMS/Lyrion).

---

## 📊 Übersicht

| Metrik | LMS (Perl) | Resonance (Python) |
|--------|------------|-------------------|
| **Codebase** | ~200.000+ LOC | ~18.500 LOC |
| **Tests** | — | 316 Tests |
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
| **Display-Befehle (grfe/grfb)** | ✅ | 📋 | Stub |
| **IR-Fernbedienung** | ✅ | 📋 | Stub |
| **UDP Discovery** | ✅ | ❌ | Nicht implementiert |

---

## 🎵 Audio & Streaming

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **MP3 Direct Streaming** | ✅ | ✅ | Vollständig |
| **FLAC Direct Streaming** | ✅ | ✅ | Vollständig |
| **OGG/Vorbis Streaming** | ✅ | ✅ | Vollständig |
| **WAV Streaming** | ✅ | ✅ | Vollständig |
| **AAC/M4A Transcoding** | ✅ | ✅ | Via faad→flac |
| **M4B (Audiobooks)** | ✅ | ✅ | Via faad→flac |
| **ALAC (Apple Lossless)** | ✅ | ❌ | Nicht implementiert |
| **WMA Transcoding** | ✅ | ❌ | Nicht implementiert |
| **DSD/DoP** | ✅ | ❌ | Nicht implementiert |
| **Gapless Playback** | ✅ | ⚠️ | Player-abhängig |
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
| **BlurHash Placeholders** | ❌ | ✅ | **Resonance-exklusiv!** |
| **Inkrementeller Rescan** | ✅ | ⚠️ | Basis (mtime-basiert) |
| **Artwork Resizing** | ✅ | ❌ | Nicht implementiert |
| **Virtual Libraries** | ✅ | ❌ | Nicht implementiert |
| **Playlists (M3U, PLS)** | ✅ | ❌ | Nicht implementiert |
| **Volltext-Suche** | ✅ | ✅ | LIKE-basiert |

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
| **Sync-Gruppen** | ✅ | ❌ | **TODO (Killer-Feature!)** |
| **Sample-genaue Sync** | ✅ | ❌ | Nicht implementiert |
| **Latenz-Kompensation** | ✅ | ❌ | Nicht implementiert |

---

## 🌐 Web-Interface & API

| Feature | LMS | Resonance | Status |
|---------|-----|-----------|--------|
| **HTTP Server** | ✅ | ✅ | FastAPI |
| **JSON-RPC API** | ✅ | ✅ | LMS-kompatibel |
| **REST API** | ⚠️ | ✅ | Resonance erweitert |
| **Cometd/Bayeux** | ✅ | ✅ | Long-Polling |
| **CLI (Telnet, Port 9090)** | ✅ | ❌ | Nicht implementiert |
| **Web-UI** | ✅ | ✅ | Svelte 5 + Tailwind v4 |
| **Material Skin** | ✅ | ❌ | Kein Plugin-System |
| **Settings/Konfiguration** | ✅ | ❌ | Nur CLI-Argumente |
| **CORS Support** | ⚠️ | ✅ | Vollständig |

---

## 📱 App-Kompatibilität

| App | LMS | Resonance | Status |
|-----|-----|-----------|--------|
| **iPeng (iOS)** | ✅ | ✅ | Getestet ✅ |
| **Squeezer (Android)** | ✅ | ✅ | Getestet ✅ |
| **Orange Squeeze** | ✅ | ⚠️ | Sollte funktionieren |
| **Cadence (Flutter)** | ❌ | ✅ | **Resonance-exklusiv!** |

---

## 🎛️ Player-Unterstützung

| Player-Typ | LMS | Resonance | Status |
|------------|-----|-----------|--------|
| **Squeezelite** | ✅ | ✅ | Vollständig getestet |
| **Squeezebox Classic** | ✅ | ⚠️ | Ungetestet |
| **Squeezebox Touch** | ✅ | ⚠️ | Ungetestet |
| **Squeezebox Radio** | ✅ | ⚠️ | Ungetestet |
| **piCorePlayer** | ✅ | ⚠️ | Ungetestet |

---

## 🔌 Plugins & Erweiterungen

| Kategorie | LMS | Resonance |
|-----------|-----|-----------|
| **Plugin-System** | ✅ (48+ Plugins) | ❌ |
| **Spotify** | ✅ (3rd-Party) | ❌ |
| **Podcasts** | ✅ | ❌ |
| **Internet Radio** | ✅ | ❌ |
| **Last.fm Scrobbling** | ✅ | ❌ |
| **Random Mix** | ✅ | ❌ |

---

## ✨ Resonance-exklusive Features

| Feature | Beschreibung |
|---------|--------------|
| **BlurHash Placeholders** | Sofortige farbige Placeholder für Cover Art |
| **Adaptive Akzentfarben** | Automatische Farbextraktion (node-vibrant) |
| **Modernes Frontend** | Svelte 5 + Tailwind v4 |
| **Cadence Desktop App** | Flutter-basierter Controller |
| **SeekCoordinator** | Latest-Wins Seek ohne Race Conditions |

---

## 📈 Zusammenfassung

### ✅ Was Resonance gut kann

- Squeezelite vollständig steuern
- Musik scannen, indizieren, durchsuchen
- Streaming (MP3, FLAC, OGG, M4A/M4B)
- LMS-kompatible Apps (iPeng, Squeezer) bedienen
- Modernes Web-UI mit Cover Art

### ❌ Was noch fehlt

- **Multi-Room Sync** — Das Killer-Feature von LMS
- **Plugin-System** — Keine Erweiterbarkeit
- **Internet Radio / Podcasts**
- **UDP Discovery** — Player müssen Server-IP kennen

### 🎯 Nächste Prioritäten

1. **Multi-Room Sync** — DAS Squeezebox-Feature
2. **UDP Discovery** — Automatische Player-Erkennung
3. **Persistente Playlists** — Save/Load
4. **Konfigurationsdatei** — server.toml

---

*Stand: Februar 2026 — 316 Tests, ~18.500 LOC*