# 🎵 Resonance — AI Bootstrap Context

> **🇩🇪 WICHTIG: Antworte IMMER auf Deutsch!**

---

## 🎯 Was ist Resonance?

**Resonance** ist eine moderne Python-Neuimplementierung des **Logitech Media Server** (LMS/SlimServer).

- **Ziel:** Volle Kompatibilität mit Squeezebox-Hardware und Software-Playern (Squeezelite)
- **Protokoll:** Slimproto (binär, Port 3483) + HTTP-Streaming (Port 9000)
- **Architektur:** Server steuert "dumme" Player — Multi-Room-Sync möglich
- **Stack:** Python 3.11+ (asyncio), FastAPI, SQLite, Svelte 5 Frontend

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Web-UI /   │ ◄──► │  Resonance  │ ◄──► │ Squeezelite │ ──► 🔊
│  Mobile App │ HTTP │   Server    │Slim- │  (Player)   │
└─────────────┘      └─────────────┘proto └─────────────┘
```

---

## 📍 Aktueller Stand

| Metrik | Wert |
|--------|------|
| **Phase** | 3 von 4 (LMS-Kompatibilität) ✅ |
| **Tests** | 356/356 bestanden ✅ |
| **Server (Python)** | ~19.000 LOC |
| **Tests** | ~7.000 LOC |
| **Web-UI (Svelte/TS)** | ~900 LOC |
| **Cadence (Flutter)** | ~6.000 LOC |

### Was funktioniert

- ✅ Slimproto-Server (Player-Steuerung)
- ✅ HTTP-Streaming mit Transcoding (MP3, FLAC, OGG, M4A/M4B)
- ✅ Musikbibliothek (Scanner, SQLite, Suche)
- ✅ JSON-RPC API (LMS-kompatibel für iPeng, Squeezer)
- ✅ Cometd/Bayeux Real-Time Updates
- ✅ Web-UI (Svelte 5 + Tailwind v4)
- ✅ Cadence Desktop App (Flutter)
- ✅ Playlist/Queue mit Shuffle/Repeat
- ✅ **Seeking mit LMS-konformer Elapsed-Berechnung** (stabil!)
- ✅ Cover Art mit BlurHash Placeholders
- ✅ **UDP Discovery** (Player finden Server automatisch)
- ✅ **aude** Audio Enable/Disable (Power on/off für Hardware)
- ✅ **JiveLite-kompatible Cover-URLs** (icon-id, icon für Radio/Touch)
- ✅ **Branding: Logos für Resonance (Vinyl) und Cadence (Kassette)**

### Cadence — Flutter Desktop App

| Was | Details |
|-----|---------|
| **Pfad** | `C:\Users\stephan\Desktop\cadence` |
| **Stack** | Flutter 3.x, Riverpod, Catppuccin Mocha Theme |
| **Plattformen** | Windows, macOS, Linux |
| **Status** | Library + Queue + Playback + Seeking funktioniert ✅ |

---

## 🔜 Nächste Schritte

| Aufgabe | Projekt | Priorität |
|---------|---------|-----------|
| grfe/grfb Display-Grafiken (Cover auf Hardware-Display) | Server | 🟢 Niedrig |
| IR-Fernbedienung Support | Server | 🟢 Niedrig |
| mDNS/Avahi Discovery (`_slimdevices._tcp`) | Server | 🟢 Niedrig |
| Cover-Placeholder Flash beheben | Cadence | 🟢 Niedrig |
| Keyboard-Shortcuts (Space=Play/Pause) | Cadence | 🟢 Niedrig |
| Search in Library | Cadence | 🟢 Niedrig |
| Fullscreen Now Playing View | Cadence | 🟢 Niedrig |
| View Transitions API | Web-UI | 🟢 Niedrig |
| Multi-Room Sync | Server | 🟢 Niedrig |

### Zuletzt erledigt

**Session: Branding Polish & Cleanup**
- ✅ **Orbitron Font**: Sci-Fi/Synthwave Typografie für beide Apps
- ✅ **Web-UI Favicon**: Vinyl-Logo als SVG
- ✅ **Self-hosted Fonts**: Orbitron lokal in `/static/fonts/` (DSGVO-konform!)
- ✅ **Cadence Logo kleiner**: 44px → 32px, Abstand reduziert
- ✅ **Windows Titelleiste**: "cadence" → "Cadence"
- ✅ **JiveLite Assets entfernt**: ~160 ungenutzte PNG-Dateien gelöscht
- ✅ **Resonance Text kleiner**: text-lg → text-base in Sidebar
- ✅ 356 Tests bestanden, Web-UI Build erfolgreich

**Session: Logos & Branding**
- ✅ **Resonance Logo**: Vinyl-Schallplatte (Cyan/Blau), inline SVG in Web-UI Sidebar
- ✅ **Cadence Logo**: Kassette (Mauve/Pink), CustomPainter in Flutter Sidebar
- ✅ **Windows App-Icon**: Multi-Size ICO (16-32px: vereinfachte zwei Spulen, 48px+: volle Kassette)
- ✅ `flutter_launcher_icons` für Icon-Generierung eingerichtet
- ✅ Logo-Dateien in `resonance-server/assets/logos/` und `cadence/assets/brand/`
- ✅ PROMPTS.md mit Bildgenerator-Prompts für alle Logo-Varianten

**Session: Play-from-STOP Fix + Web-UI UX**
- ✅ **LMS-like `play` Befehl**: Bei STOP + Queue startet jetzt der aktuelle Playlist-Track (nicht nur Resume)
- ✅ Regression-Test für play-from-stop (356 Tests gesamt)
- ✅ Web-UI: Album Action Bar mit Play/Shuffle/Add to Queue Buttons
- ✅ Web-UI: + Button bei Tracks fügt einzelnen Track zur Queue hinzu
- ✅ Web-UI: Workaround entfernt (Server ist jetzt korrekt)
- ✅ Web-UI: Cadence-Style Elapsed-Interpolation mit Slew-rate Limiting
- ✅ Web-UI: pendingSeek verhindert Polling-Konflikte beim Seeking

**Session: Web-UI Verbesserungen (Cadence-Style)**
- ✅ Robustere Elapsed-Time-Interpolation mit Slew-rate Limiting
- ✅ Monotonic Clamp verhindert Rückwärts-Jitter beim Progress-Bar
- ✅ Track-Change-Detection mit Hard-Reset bei großen Sprüngen
- ✅ Seek mit pendingSeek-Flag verhindert Polling-Konflikte
- ✅ TypeScript-Typen für playlist_loop gefixt (coverArt, artwork_url)
- ✅ svelte.config.js: handleHttpError für fehlendes favicon
- ✅ Build erfolgreich, alle 355 Tests bestanden

**Session: Hardware-Support & JiveLite-Kompatibilität**
- ✅ UDP Discovery IPAD-Bug gefixt (Server meldet jetzt IP korrekt)
- ✅ JiveLite-kompatible Cover-URLs (`icon-id`, `icon`, `artwork_track_id`)
- ✅ `/music/{id}/cover` Route hinzugefügt (ohne .jpg Extension)
- ✅ `aude` Audio Enable/Disable implementiert (Power on/off)
- ✅ 6 neue Tests für `aude` (355 Tests gesamt)
- ✅ "Playing:" SnackBars in Cadence entfernt

**Vorherige Session (ChatGPT Deep Code Review):**
- ✅ Byte-Offset-Seeks setzen jetzt `start_offset` für korrektes Elapsed-Reporting
- ✅ `time ?` liefert jetzt korrektes elapsed (start_offset + raw)
- ✅ Reader-Thread join im Transcoder (verhindert Thread-Leak auf Windows)
- ✅ UDP Discovery Server auf Port 3483 implementiert
- ✅ 31 Tests für Discovery-Protokoll

---

## ⚡ Quick Start

```powershell
# Server starten
cd resonance-server
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --verbose

# Web-UI starten (separates Terminal)
cd resonance-server/web-ui
npm run dev
# → http://localhost:5173/

# Cadence starten
cd C:\Users\stephan\Desktop\cadence
flutter run -d windows

# Tests ausführen
cd resonance-server
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v
```

---

## 🎨 Branding

| Projekt | Logo | Farben | Dateien |
|---------|------|--------|---------|
| **Resonance** | Vinyl 💿 | Cyan `#06b6d4` → Blau `#3b82f6` | `resonance-server/assets/logos/` |
| **Cadence** | Kassette 📼 | Mauve `#CBA6F7` → Pink `#F5C2E7` | `cadence/assets/brand/` |

**Icon-Strategie:**
- **Titelleiste (16-32px):** Vereinfachtes Symbol (nur zwei Spulen-Kreise)
- **Sidebar (44px+):** Volles Logo mit Details
- **Splash/About (128px+):** Volles Logo + Text

---

## 📂 Projektstruktur

```
resonance-server/
├── resonance/                    # Hauptpaket (~18.500 LOC)
│   ├── server.py                 # Haupt-Server, startet alle Komponenten
│   ├── config/                   # Konfiguration (devices.toml, legacy.conf)
│   ├── core/                     # Business Logic
│   │   ├── library.py            # MusicLibrary Facade
│   │   ├── library_db.py         # SQLite DB Layer
│   │   ├── scanner.py            # Audio-Datei Scanner
│   │   ├── playlist.py           # Playlist/Queue Management
│   │   ├── artwork.py            # Cover Art + BlurHash
│   │   ├── events.py             # Event-Bus (pub/sub)
│   │   └── db/                   # DB Schema & Queries
│   ├── player/                   # Player-Verwaltung
│   │   ├── client.py             # PlayerClient Klasse
│   │   └── registry.py           # PlayerRegistry
│   ├── protocol/                 # Slimproto-Protokoll
│   │   ├── slimproto.py          # SlimprotoServer, STM Event Handling
│   │   └── commands.py           # strm, audg, etc. Builder
│   ├── streaming/                # Audio-Streaming
│   │   ├── server.py             # StreamingServer, start_offset
│   │   ├── transcoder.py         # Transcoding Pipeline (faad, flac, lame)
│   │   ├── seek_coordinator.py   # Latest-Wins Seek-Koordination
│   │   └── policy.py             # Transcoding-Entscheidungen
│   └── web/                      # HTTP/API Layer
│       ├── server.py             # FastAPI App
│       ├── jsonrpc.py            # JSON-RPC Handler
│       ├── cometd.py             # Bayeux Long-Polling
│       ├── handlers/             # Command Handlers
│       │   ├── status.py         # Player-Status (elapsed = start_offset + raw)
│       │   ├── seeking.py        # Seek-Befehle (non-blocking!)
│       │   ├── playback.py       # Play/Pause/Stop
│       │   ├── playlist.py       # Queue-Befehle
│       │   └── library.py        # Library-Abfragen
│       └── routes/               # FastAPI Routes
├── tests/                        # Tests (~6.400 LOC, 316 Tests)
├── web-ui/                       # Svelte 5 Frontend
└── docs/                         # Dokumentation

cadence/                          # Flutter Desktop App
├── lib/
│   ├── api/resonance_client.dart # HTTP + JSON-RPC Client
│   ├── providers/providers.dart  # Riverpod State Management
│   ├── screens/                  # UI Screens
│   └── widgets/                  # Reusable Widgets
```

---

## 🚨 KRITISCHE FALLSTRICKE

### 1. LMS-kompatible Seek-Elapsed-Berechnung 🚨

Nach Seek reportet Squeezelite `elapsed` **relativ zum Stream-Start** (0, 1, 2...), nicht zur Track-Position!

**LMS-Formel:** `elapsed = start_offset + raw_elapsed`

```python
# In status.py:
start_offset = streaming_server.get_start_offset(player_mac)  # Seek-Position
raw_elapsed = player.status.elapsed_seconds                    # Vom Player
actual_elapsed = start_offset + raw_elapsed                    # Echte Position
```

### 2. STM Event Handling (LMS-konform) 🚨

| Event | Bedeutung | Aktion |
|-------|-----------|--------|
| `STMs` | Track **S**tarted | → PLAYING |
| `STMp` | **P**ause | → PAUSED |
| `STMr` | **R**esume | → PLAYING |
| `STMf` | **F**lush | → **KEIN** State-Change! |
| `STMd` | **D**ecode ready | → **KEIN** Auto-Advance! |
| `STMu` | **U**nderrun | → STOPPED + Track-Finished |

**Wichtig:** Nur `STMu` triggert Track-Finished/Auto-Advance!

### 3. Pause muss LMS-konform sein 🚨

```dart
// Cadence: Explizite Befehle statt Toggle
await client.pause(playerId);   // pause 1
await client.resume(playerId);  // pause 0
```

### 3b. Next/Previous muss `playlist jump` verwenden 🚨

```dart
// ❌ FALSCH - funktioniert nicht zuverlässig
await _jsonRpc(playerId, ['playlist', 'index', '+1']);

// ✅ RICHTIG - LMS-kompatibel
await _jsonRpc(playerId, ['playlist', 'jump', '+1']);
```

### 3c. playAlbum: loadtracks startet automatisch 🚨

```dart
// ❌ FALSCH - redundante Befehle, Race Conditions
await _jsonRpc(playerId, ['playlist', 'loadtracks', 'album_id:$albumId']);
await _jsonRpc(playerId, ['playlist', 'index', 0]);
await _jsonRpc(playerId, ['play']);

// ✅ RICHTIG - Server macht auto-start
await _jsonRpc(playerId, ['playlist', 'loadtracks', 'album_id:$albumId']);
```

### 3d. `play` bei STOP startet Queue-Track 🚨

Bei STOP + nicht-leerer Queue startet `play` den **aktuellen** Playlist-Track (LMS-like):

```python
# In playback.py cmd_play():
if is_stopped and playlist is not None and len(playlist) > 0:
    track = playlist.play(playlist.current_index)
    await _start_track_stream(ctx, player, track)  # Startet Stream!
else:
    await player.play()  # Fallback: Resume
```

### 4. Seek darf JSON-RPC nicht blockieren 🚨

```python
# In seeking.py cmd_time():
asyncio.create_task(run_seek())  # Fire-and-forget
return {"_time": target_time}    # Sofort antworten
```

### 5. Python Falsy-Falle 🚨

```python
# ❌ FALSCH
if playlist:  # Leere Liste = False!

# ✅ RICHTIG
if playlist is not None:
```

### 6. cancel_stream() NIEMALS nach queue_file() 🚨

`queue_file()` erhöht die Stream-Generation. Danach `cancel_stream()` = Self-Cancel!

### 7. micromamba statt venv 🚨

```powershell
# ✅ RICHTIG
micromamba run -p ".build/mamba/envs/resonance-env" python ...

# ❌ FALSCH - System-Python!
python ...
```

### 8. NIEMALS `git checkout -- .` ohne Backup 🚨

```powershell
# ❌ NIEMALS - Verliert alle uncommitted Änderungen!
git checkout -- .

# ✅ RICHTIG - Erst committen oder stashen
git stash
# oder
git add -A && git commit -m "WIP: checkpoint before changes"
```

---

## 🖥️ Häufige Befehle

```powershell
# Tests
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest tests/test_player.py -v

# Linting
micromamba run -p ".build/mamba/envs/resonance-env" ruff check --fix resonance/

# Web-UI
cd web-ui && npm run check && npm run build

# Cadence
cd C:\Users\stephan\Desktop\cadence && flutter analyze && flutter run -d windows

# Git
git status && git --no-pager diff && git --no-pager log --oneline -5
```

---

## 📂 Wichtige Pfade

| Was | Pfad |
|-----|------|
| **Resonance Server** | `resonance-server/` |
| **Cadence (Flutter)** | `C:\Users\stephan\Desktop\cadence` |
| **JiveLite (Referenz)** | `jivelite-master/` |
| **Original SlimServer** | `slimserver-public-9.1/` (Perl-Referenz) |
| **micromamba Env** | `resonance-server/.build/mamba/envs/resonance-env` |

---

## 🔍 LMS-Referenz nachschlagen

```powershell
# Beispiel: Wie macht LMS das?
grep(regex="sub pause", include_pattern="slimserver-public-9.1/**/*.pm")
read_file(path="slimserver-public-9.1/Slim/Player/Client.pm")
```

Wichtige LMS-Dateien:
- `Slim/Player/StreamingController.pm` — Elapsed-Berechnung, startOffset
- `Slim/Player/Squeezebox2.pm` — STM Event Handling
- `Slim/Control/Commands.pm` — CLI-Befehle

---

## 📋 Decision Log

| Entscheidung | Begründung |
|--------------|------------|
| LMS-kompatible Elapsed | `elapsed = start_offset + raw_elapsed` — Siehe `SEEK_ELAPSED_FINDINGS.md` |
| SeekCoordinator | Latest-Wins, 50ms Coalescing, saubere Subprocess-Termination |
| STMu für Track-Finished | Nur STMu triggert Auto-Advance (wie LMS `playerStopped()`) |
| Python + asyncio | Modern, gute Library-Unterstützung |
| Svelte 5 + Tailwind v4 | Modernes Frontend, kleine Bundles |
| Flutter für Cadence | Cross-Platform Desktop, Riverpod für State |
| Resonance: GPL v2 | LMS-Community Kompatibilität |
| Cadence: BSD-3-Clause | Wie JiveLite (dessen Icons wir nutzen) |
| `playlist jump` statt `index` | LMS-konform, zuverlässiger für Next/Previous |
| `loadtracks` ohne extra play | Server startet automatisch nach loadtracks |
| LMS-Style cancel_token | Kein Stream-Lock, cancel_token bricht alte Streams ab |
| Sync Pipeline Cleanup | `_cleanup_popen_pipeline_sync()` - kein await im finally-Block |
| Slider: onChangeEnd | Seek nur bei Release, nicht bei jeder Mausbewegung |
| Byte-Offset + start_offset | Auch MP3/FLAC/OGG Seeks setzen start_offset für korrektes elapsed |
| `time ?` korrigiert | Query-Mode liefert jetzt auch start_offset + raw_elapsed |
| Thread-Leak Fix | reader_thread.join(timeout=0.1) im Transcoder-Finally |
| UDP Discovery | Player finden Server automatisch via Broadcast (Port 3483) |
| `aude` für Power | Audio-Outputs werden bei Power on/off aktiviert/deaktiviert |
| JiveLite Cover-URLs | `icon-id`, `icon` für Squeezebox Radio/Touch Kompatibilität |
| Web-UI: Cadence-Style Smoothing | Slew-rate limiting + monotonic clamp für flüssige Progress-Bar |
| Web-UI: pendingSeek | Verhindert Polling-Konflikte während Seek-Operationen |
| `play` LMS-like bei STOP | Bei STOP + Queue startet `play` den aktuellen Playlist-Track (nicht nur Resume) |
| Web-UI: Album Action Bar | Play/Shuffle/Add to Queue Buttons über Track-Liste |
| Resonance Logo: Vinyl | Cyan/Blau, inline SVG, optimiert für kleine Größen |
| Cadence Logo: Kassette | Mauve/Pink, CustomPainter, Multi-Size Icons |
| Icon-Strategie | 16-32px vereinfacht (zwei Kreise), 48px+ voll (Kassette) |
| Orbitron Font | Sci-Fi/Synthwave Typografie für Brand-Namen |
| Self-hosted Fonts | DSGVO-konform, keine Google-Server-Anfragen |
| JiveLite Assets entfernt | Ungenutzte hdskin/toolbar/nowplaying PNGs gelöscht |

---

## 🚀 WHKTM-Protokoll

Wenn der Mensch sagt **"whktm"** oder **"wir haben keine tokens mehr"**:

1. **SOFORT dokumentieren:** AI_BOOTSTRAP.md + CHANGELOG.md aktualisieren
2. **Dem Menschen sagen:** `Nächste Session: "Lies AI_BOOTSTRAP.md und mach weiter"`

---

## ✅ Session-Ende-Checkliste

- [ ] Tests grün? (`pytest -v`)
- [ ] Docs aktualisiert?
- [ ] Neue Fallstricke dokumentiert?
- [ ] Nächste Schritte klar?

---

## 🚫 Was die AI NICHT tun darf

1. Kein Refactoring ohne grüne Tests
2. Keine API-Änderungen ohne LMS-Vergleich
3. Keine neuen Dependencies ohne Rückfrage
4. Keine Dateien löschen ohne Backup
5. Keine "Vereinfachungen" die Features entfernen
6. **NIEMALS `git checkout -- .` oder `git reset --hard` ohne explizite Bestätigung!**

---

## 📚 Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [COLDSTART.md](./COLDSTART.md) | **Minimaler Einstieg** (Token-sparend) |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System-Architektur, Protokolle, Code-Struktur |
| [SEEK_ELAPSED_FINDINGS.md](./SEEK_ELAPSED_FINDINGS.md) | LMS-konforme Seek/Elapsed Implementierung |
| [SLIMPROTO.md](./SLIMPROTO.md) | Binärprotokoll Details, Message-Format |
| [COMPARISON_LMS.md](./COMPARISON_LMS.md) | Feature-Vergleich mit Original LMS |
| [E2E_TEST_GUIDE.md](./E2E_TEST_GUIDE.md) | Testen mit echten Apps (iPeng, Squeezer) |
| [CHANGELOG.md](./CHANGELOG.md) | Änderungshistorie |
| [ECOSYSTEM.md](./ECOSYSTEM.md) | Squeezebox Hardware/Software Übersicht |

> **Tipp:** Für schnellen Session-Start mit wenig Tokens: `Lies COLDSTART.md`
