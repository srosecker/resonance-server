# 📋 Resonance Changelog

Alle wesentlichen Änderungen am Projekt werden hier dokumentiert.

---

## [Unreleased] — Phase 3 Abgeschlossen ✅

**Stand:** 356/356 Tests bestanden | ~19.000 LOC Python | ~6.000 LOC Flutter

### ✅ Play-from-STOP Fix + Web-UI UX (2026-02-06)

**Problem:** Wenn der Player gestoppt war und Tracks in der Queue lagen, startete
der `play`-Befehl nicht zuverlässig — Track wurde kurz angespielt, dann Abbruch.

**Root Cause:** `cmd_play()` im Server machte nur `await player.play()` (Resume),
aber startete **keinen Stream** aus der Playlist bei STOP-State.

**Fix (LMS-like):**
- `play` bei STOP + nicht-leere Queue → `playlist.play(current_index)` + `_start_track_stream()`
- Fallback bei PLAYING/PAUSED → `player.play()` (Resume wie bisher)

**Weitere Änderungen:**
- Regression-Test hinzugefügt (356 Tests gesamt)
- Web-UI: Album Action Bar mit **Play / Shuffle / Add to Queue** Buttons
- Web-UI: **+** Button bei Tracks fügt einzelnen Track zur Queue hinzu
- Web-UI: Workaround in `playerStore.play()` entfernt (Server ist jetzt korrekt)

### ✅ Web-UI Verbesserungen: Cadence-Style Smoothing (2026-02-06)

**Problem:** Progress-Bar im Web-UI war weniger flüssig als in Cadence (Flutter)

**Lösung:** Cadence-Style Elapsed-Time-Interpolation portiert:

1. **Slew-rate Limiting**
   - Forward: max 0.025s pro Frame (1.5x Geschwindigkeit)
   - Backward: max 0.012s pro Frame (nur bei Server-Korrektur)
   - Verhindert Jitter und abrupte Sprünge

2. **Monotonic Clamp**
   - Verhindert kleine Rückwärts-Bewegungen (<0.1s)
   - Sorgt für flüssige Vorwärtsbewegung

3. **Track-Change-Detection**
   - Erkennt Track-Wechsel und große Sprünge (>1.5s)
   - Hard-Reset der Smoothing-State bei Erkennung

4. **pendingSeek Flag**
   - Verhindert Polling während Seek-Operationen
   - Kein "Zurückspringen" nach Seek

**Weitere Fixes:**
- TypeScript-Typen für `playlist_loop` erweitert (`coverArt`, `artwork_url`)
- `svelte.config.js`: `handleHttpError` für fehlendes favicon
- Build erfolgreich, alle 355 Tests bestanden

### ✅ Behoben: Rapid Seeking Blocking (2026-02-05)

**Problem:** Rapid Seeking führte zu App-Hänger (Timeouts nach mehreren schnellen Seeks)

**Root Causes & Fixes:**

1. **Stream-Lock entfernt (LMS-Style)**
   - `streaming.py` verwendete einen `asyncio.Lock` pro Player
   - LMS macht das anders: Schließt alten Stream sofort, öffnet neuen - KEIN Lock!
   - Fix: Lock entfernt, Streams laufen kurz parallel, alter bricht via `cancel_token` ab

2. **Pipeline Cleanup synchron gemacht**
   - `_cleanup_popen_pipeline_sync()` statt async Version
   - Kein `await`, kein `create_task` im finally-Block
   - Direkt `close()` und `kill()` - blockiert nicht bei CancelledError

3. **SeekCoordinator Deadlock behoben**
   - Lock-Acquisition mit 500ms Timeout
   - Alte Tasks werden nicht mehr awaited beim Canceln
   - Coalesce-Delay von 50ms auf 20ms reduziert

4. **Slider: Seek nur bei Release** (Cadence)
   - Neuer `_SeekSlider` Widget mit `onChangeEnd` statt `onChanged`
   - Während Dragging: nur lokale Anzeige-Update
   - Bei Loslassen: einziger Seek-Request (statt 100+ während Drag)

5. **stderr-Lesen bei Cancellation entfernt**
   - `_log_popen_stderr` wird bei CancelledError nicht mehr aufgerufen
   - Verhindert Blocking auf noch laufende Prozesse

**Weitere Fixes dieser Session:**
- `playlist index` → `playlist jump` für Next/Previous (LMS-konform)
- `playAlbum`: Redundante `index 0` + `play` Befehle entfernt (loadtracks macht auto-start)
- "Playing:" SnackBar Nachrichten entfernt
- Play-Icon Overlay auf Album-Cards entfernt

### 🎵 Cadence Desktop App (Flutter)

Vollständige Desktop-App als Controller für Resonance:

- Server-Verbindung mit Auto-Connect
- Player-Auswahl Dropdown
- Library Browser (Artists → Albums → Tracks) mit Breadcrumb-Navigation
- Now Playing Bar mit Seek-Slider
- Queue-View mit Drag & Drop
- Playback Controls (Play/Pause/Next/Previous/Volume)
- LMS-konforme Pause/Resume Semantik (`pause 1` / `pause 0`)
- Catppuccin Mocha Theme
- Debug-Logging für Seek-Operationen (`[SEEK]`, `[API-SEEK]`)

### 🔧 Server-Kern

- **Slimproto-Server** — Vollständige Implementierung (Port 3483)
- **HTTP-Streaming** — Range Requests, Transcoding (Port 9000)
- **JSON-RPC API** — LMS-kompatibel für iPeng, Squeezer, Orange Squeeze
- **Cometd/Bayeux** — Long-Polling für Real-Time Updates
- **Musikbibliothek** — Scanner, SQLite, Suche, Genres, Contributors
- **Playlist/Queue** — Add, Remove, Shuffle, Repeat (Off/One/All)

### 🔊 Streaming & Transcoding

- **Formate:** MP3, FLAC, OGG, WAV (direct) + M4A, M4B, AAC (via faad→flac/mp3)
- **SeekCoordinator** — Latest-Wins-Semantik, 50ms Coalescing
- **Policy-System** — Zentrale Transcoding-Entscheidungen
- **Range Requests** — Vollständiges Seeking
- **Debug-Logging** — `[STREAM-LOCK]`, `[TRANSCODE]` Tags für Diagnose

### 🎨 Web-UI (Svelte 5)

- Svelte 5 mit Runes ($state, $derived)
- Tailwind CSS v4
- Cover Art mit BlurHash Placeholders
- Adaptive Akzentfarben (node-vibrant)
- Resizable Sidebar & Queue Panels
- Now Playing mit Progress Bar, Volume Slider

### 🐛 Wichtige Fixes

- **LMS-konformes STM Event Handling** — STMu = Track-Ende, STMf = kein State-Change
- **Elapsed-Berechnung** — `elapsed = start_offset + raw_elapsed` (wie LMS)
- **Non-blocking Seek** — JSON-RPC antwortet sofort, Seek läuft im Hintergrund
- **BlurHash Cache-Only** — Status-Endpoint blockiert nicht mehr

---

## [0.1.0] — Erste Funktionierende Version

### Meilensteine

1. **Slimproto-Verbindung** — Squeezelite verbindet und bleibt stabil
2. **Audio-Streaming** — Erste Wiedergabe über HTTP
3. **Transcoding** — M4B/M4A funktioniert via faad
4. **Web-UI** — Modernes Svelte 5 Frontend
5. **Cometd** — Real-Time Updates für Apps
6. **Cadence** — Flutter Desktop App gestartet

---

## Versionsschema

Wir folgen [Semantic Versioning](https://semver.org/):

- **MAJOR:** Inkompatible API-Änderungen
- **MINOR:** Neue Features, rückwärtskompatibel
- **PATCH:** Bugfixes

---

## 🔗 Verwandte Dokumente

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Technische Architektur
- [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md) — AI-Kontext
- [COMPARISON_LMS.md](./COMPARISON_LMS.md) — Feature-Vergleich mit LMS

---

*Zuletzt aktualisiert: Februar 2026*