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
| **Phase** | 3 von 4 (LMS-Kompatibilität) |
| **Tests** | 356/356 bestanden ✅ |
| **Server (Python)** | ~19.000 LOC |
| **Web-UI (Svelte/TS)** | ~900 LOC |
| **Cadence (Flutter)** | ~6.000 LOC |

### Was funktioniert ✅

- Slimproto-Server (Player-Steuerung)
- HTTP-Streaming mit Transcoding (MP3, FLAC, OGG, M4A/M4B)
- Musikbibliothek (Scanner, SQLite, Suche)
- JSON-RPC API (LMS-kompatibel für iPeng, Squeezer)
- Cometd/Bayeux Real-Time Updates (Streaming + Long-Polling)
- Web-UI (Svelte 5 + Tailwind v4)
- Cadence Desktop App (Flutter)
- Playlist/Queue mit Shuffle/Repeat
- Seeking mit LMS-konformer Elapsed-Berechnung
- Cover Art mit BlurHash Placeholders + Resize-Spec (`/music/{id}/cover_41x41_m`)
- UDP Discovery (Player finden Server automatisch)
- Jive Menu System (für Squeezebox Radio/Touch/Boom)

### Cadence — Flutter Desktop App

| Was | Details |
|-----|---------|
| **Pfad** | `C:\Users\stephan\Desktop\cadence` |
| **Stack** | Flutter 3.x, Riverpod, Catppuccin Mocha Theme |
| **Plattformen** | Windows, macOS, Linux |

---

## 🔜 Nächste Schritte

| Aufgabe | Projekt | Priorität |
|---------|---------|-----------|
| ~~Live-Test: Streaming auf Squeezebox Radio~~ | Server | ✅ Erledigt |
| **Live-Test: Fixes vom 2026-02-06 verifizieren (Playlist-Nichts + Cometd)** | Server | 🔴 Hoch |
| displaystatus-Befehl implementieren (WARNING im Log) | Server | 🟡 Mittel |
| Shipping: pip/PyPI Setup | Server | 🟡 Mittel |
| Shipping: Docker Image | Server | 🟡 Mittel |
| grfe/grfb Display-Grafiken (Cover auf Hardware) | Server | 🟢 Niedrig |
| Multi-Room Sync | Server | 🟢 Niedrig |

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

| Projekt | Logo | Farben |
|---------|------|--------|
| **Resonance** | Vinyl 💿 | Cyan `#06b6d4` → Blau `#3b82f6` |
| **Cadence** | Kassette 📼 | Mauve `#CBA6F7` → Pink `#F5C2E7` |

---

## 📂 Projektstruktur

```
resonance-server/
├── resonance/                    # Hauptpaket
│   ├── server.py                 # Haupt-Server
│   ├── core/                     # Business Logic (library, playlist, artwork)
│   ├── player/                   # Player-Verwaltung (client, registry)
│   ├── protocol/                 # Slimproto + Discovery
│   ├── streaming/                # Audio-Streaming + Transcoding
│   └── web/                      # HTTP/API Layer (FastAPI, JSON-RPC, Cometd)
├── tests/                        # Tests (~356)
├── web-ui/                       # Svelte 5 Frontend
└── docs/                         # Dokumentation

cadence/                          # Flutter Desktop App
├── lib/
│   ├── api/resonance_client.dart # HTTP + JSON-RPC Client
│   ├── providers/                # Riverpod State Management
│   └── screens/                  # UI Screens
```

---

## 🚨 KRITISCHE FALLSTRICKE

### 1. LMS-kompatible Seek-Elapsed-Berechnung 🚨

Nach Seek reportet Squeezelite `elapsed` **relativ zum Stream-Start**, nicht zur Track-Position!

```python
# LMS-Formel:
elapsed = start_offset + raw_elapsed
```

### 2. STM Event Handling 🚨

| Event | Bedeutung | Aktion |
|-------|-----------|--------|
| `STMs` | Track Started | → PLAYING |
| `STMp` | Pause | → PAUSED |
| `STMr` | Resume | → PLAYING |
| `STMf` | Flush | → KEIN State-Change! |
| `STMu` | Underrun | → STOPPED + Track-Finished |

**Wichtig:** Nur `STMu` triggert Track-Finished/Auto-Advance!

### 3. Track Menu "go" Action 🚨

Squeezebox Radio verwendet `"go"` Action bei Enter/OK, NICHT `"play"`:
```python
# Track-Items brauchen explizite "go" Action:
"actions": {
    "go": {"cmd": ["playlistcontrol"], "params": {"cmd": "load", "track_id": X}, "nextWindow": "nowPlaying"},
    "play": {...}
}
```

### 4. Cover-Route: album_id NICHT track_id 🚨

`/music/{id}/cover` wird von Squeezeboxen angefordert. Die ID ist die **album_id** (aus `icon-id`), NICHT track_id!
```python
# Route sucht zuerst nach album_id, dann fallback track_id:
rows = await db.list_tracks_by_album(album_id=artwork_id, ...)
if not rows:
    row = await db.get_track_by_id(artwork_id)  # Fallback
```

### 5. Volume seq_no für Sync 🚨

SqueezePlay sendet `seq_no` bei Volume-Änderungen. Server MUSS diese:
1. Im `audg` Frame zurücksenden
2. Im `status` Response zurückgeben
```python
# mixer volume 50 seq_no:22
frame = build_volume_frame(volume, seq_no=seq_no)  # seq_no wird angehängt
result["seq_no"] = player._seq_no  # In status Response
```

### 6. playlist_loop IMMER aufbauen 🚨

`playlist_loop` muss AUSSERHALB von `if current_track is not None:` aufgebaut werden!
Sonst ist "Aktuelle Wiedergabeliste" leer wenn Track gerade erst hinzugefügt wurde.

### 7. VERS = "7.999.999" 🚨

SqueezePlay Firmware 7.7.3 hat Version-Bug — Versionen >= 8.0.0 werden abgelehnt!

### 8. micromamba statt venv 🚨

```powershell
# ✅ RICHTIG
micromamba run -p ".build/mamba/envs/resonance-env" python ...

# ❌ FALSCH - System-Python!
python ...
```

### 9. NIEMALS `git checkout -- .` ohne Backup 🚨

```powershell
# ✅ RICHTIG - Erst committen oder stashen
git stash
git add -A && git commit -m "WIP: checkpoint"
```

### 10. faad.exe IST bereits LMS-gepatcht 🚨

Das `faad.exe` in `third_party/bin/` ist die **LMS-gepatchte Version** von Ralph Irving
mit ALAC-, Seeking- und Chapter-Support. NICHT durch ffmpeg ersetzen!

```powershell
# Beweis:
./third_party/bin/faad.exe 2>&1 | Select-String "Patched"
# → "Patched for Squeezebox Server"
# → Source: https://github.com/ralph-irving/faad2
```

### 11. Server-Log Zeilen sind oft ABGESCHNITTEN 🚨

Das `--verbose` Terminal-Log kürzt lange Zeilen. Der Transcode-Counter loggt nur
Chunks 1-3 und jeden 100. — dazwischen fehlen Logs. Die finale "Transcode complete"
Zeile kann abgeschnitten sein und falsche Byte-Zahlen suggerieren.

**IMMER pcapng/Wireshark zur Verifikation der tatsächlich gesendeten Bytes nutzen!**

```powershell
# TCP-Daten auf Stream-Port verifizieren:
& "C:/Program Files/Wireshark/tshark.exe" -r capture.pcapng `
  -Y "tcp.port==51299 && tcp.srcport==9000 && tcp.len > 0" `
  -T fields -e tcp.len | awk '{sum += $1} END {print sum}'
```

---

## 📂 Wichtige Pfade

| Was | Pfad |
|-----|------|
| **Resonance Server** | `resonance-server/` |
| **Cadence (Flutter)** | `C:\Users\stephan\Desktop\cadence` |
| **JiveLite (Referenz)** | `jivelite-master/` |
| **Original SlimServer** | `slimserver-public-9.1/` (Perl-Referenz) |

---

## 🔍 LMS-Referenz nachschlagen

```powershell
# Beispiel: Wie macht LMS das?
grep -r "sub pause" slimserver-public-9.1/Slim/
```

Wichtige LMS-Dateien:
- `Slim/Player/StreamingController.pm` — Elapsed-Berechnung
- `Slim/Player/Squeezebox2.pm` — STM Event Handling
- `Slim/Control/Commands.pm` — CLI-Befehle
- `Slim/Control/XMLBrowser.pm` — Jive Menu Actions

---

## 📋 Wichtige Entscheidungen

| Entscheidung | Begründung |
|--------------|------------|
| Track "go" Action | SqueezePlay verwendet `"go"` nicht `"play"` bei Enter/OK |
| Cover Resize Spec | `/music/{id}/cover_{WxH}_{mode}` für LMS-Kompatibilität |
| VERS = "7.999.999" | Firmware-Bug Workaround |
| LAN-IP via UDP-Trick | Server meldet echte LAN-IP statt 127.0.0.1 |
| TCP Keepalive 10s/5s | Verhindert WinError 121 auf Windows |
| UUID v4 (36 Zeichen) | LMS-kompatibles Format |
| Streaming Cometd | Squeezebox erwartet `connectionType: "streaming"` |
| faad statt ffmpeg | LMS-gepatchtes faad2 in third_party/bin/ funktioniert korrekt |
| Cometd Timeout 1h | 300s war zu kurz, Radio verlor Push-Verbindung |

---

## 🚀 WHKTM-Protokoll

Wenn der Mensch sagt **"whktm"** oder **"wir haben keine tokens mehr"**:

1. **SOFORT dokumentieren:** AI_BOOTSTRAP.md aktualisieren
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
5. **NIEMALS `git checkout -- .` ohne explizite Bestätigung!**

---

## 📚 Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [COLDSTART.md](./COLDSTART.md) | Minimaler Einstieg (Token-sparend) |
| [SQUEEZEBOX_RADIO_PROTOCOL.md](./SQUEEZEBOX_RADIO_PROTOCOL.md) | Komplette Protokoll-Doku |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System-Architektur |
| [SEEK_ELAPSED_FINDINGS.md](./SEEK_ELAPSED_FINDINGS.md) | Seek/Elapsed Implementierung |
| [SLIMPROTO.md](./SLIMPROTO.md) | Binärprotokoll Details |

> **Tipp:** Für schnellen Session-Start: `Lies COLDSTART.md`

---

## 📝 Session-Log: 2026-02-06 — Squeezebox Radio Live-Test Analyse

### Angewandte Fixes (Tests: 356/356 ✅)

**Fix 1: Playlist zeigt "Nichts" statt Track-Info** — `resonance/web/handlers/playlist.py`
```python
# In _playlist_loadtracks(): Dict-Keys korrigiert (TrackRow-Feldnamen)
artist_name=row_dict.get("artist"),   # war: "artist_name" → None
album_title=row_dict.get("album"),    # war: "album_title" → None
```

**Fix 2: Cometd Streaming Timeout** — `resonance/web/routes/cometd.py`
- `STREAMING_TIMEOUT`: 300 → 3600 (1 Stunde statt 5 Minuten)
- Reconnect-Advice am Stream-Ende hinzugefügt (`"reconnect": "retry"`)

**Fix 3: build_command() ffmpeg-kompatibel** — `resonance/streaming/transcoder.py`
- `$START$`/`$END$` Substitution ist jetzt binary-aware: `-ss`/`-to` für ffmpeg, `-j`/`-e` für faad
- Zukunftssicher, aktuell nicht gebraucht (faad funktioniert)

### Korrigierte Fehldiagnose: "12KB Transcode Bug"

Die Session-Findings-Analyse vom Coding Agent behauptete, faad liefere nur 12KB.
**pcapng-Analyse beweist: Das war FALSCH!**

| Quelle | Bytes | Erklärung |
|--------|-------|-----------|
| Server-Log (abgeschnitten) | "12288" | Nur Chunks 1-3 geloggt, Finalzeile abgeschnitten |
| **pcapng (Ground Truth)** | **201.038** | TCP Seq-Analyse: vollständige ~12s MP3 |
| Player STMu elapsed | 12s | Track lief korrekt bis zum Ende |

**Das LMS-gepatchte faad2 funktioniert einwandfrei.** NICHT durch ffmpeg ersetzen!

### Was "System unbenutzbar" verursachte

Nach Track-Ende (STMu) + Cometd-Timeout (5min) hatte die Radio keine Push-Verbindung
mehr zum Server → keine Events, keine Navigation möglich. Fix: Timeout auf 1h erhöht.

### Referenz-Dateien

- `docs/ws32.pcapng` — Wireshark-Capture des Live-Tests
- `docs/ws32_server.txt` — Server-Log (1545 Zeilen, Zeilen ABGESCHNITTEN)
