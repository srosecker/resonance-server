# 🧪 End-to-End Test Guide

Diese Anleitung beschreibt, wie man Resonance mit echten LMS-Apps (iPeng, Squeezer, etc.) und Squeezelite testet.

---

## 📋 Voraussetzungen

- Resonance-Server läuft
- Squeezelite installiert (für Audio-Ausgabe)
- LMS-kompatible App (iPeng, Squeezer, Material Skin, etc.)
- Alle Geräte im selben Netzwerk

---

## 🚀 Server starten

```powershell
cd resonance-server
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --verbose

# Mit Music-Root:
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --music-root "D:\Musik"
```

Der Server startet:
- **Slimproto**: Port 3483 (für Player-Kommunikation)
- **HTTP/JSON-RPC**: Port 9000 (für Apps + Streaming)

---

## 🔊 Squeezelite starten

### Windows

```powershell
cd resonance-server
.\third_party\squeezelite\squeezelite-ffmpeg-x64.exe -s 127.0.0.1 -o "WASAPI" -C 5
```

**Parameter:**
- `-s 127.0.0.1` — Server-IP (localhost für lokalen Test)
- `-o "WASAPI"` — Audio-Ausgabe (oder `-o -` für Standardausgabe)
- `-C 5` — Reconnect-Timeout in Sekunden

### Liste der Audiogeräte anzeigen

```powershell
cd resonance-server
.\third_party\squeezelite\squeezelite-ffmpeg-x64.exe -l
```

### Linux/macOS

```bash
squeezelite -s 127.0.0.1 -o default -C 5
```

---

## 📱 App-Konfiguration

### iPeng (iOS)

1. Öffne iPeng
2. Gehe zu **Einstellungen** → **Server**
3. Wähle **Manuell hinzufügen**
4. Gib die Server-IP ein (z.B. `192.168.1.100`)
5. Port: `9000` (Standard)
6. Speichern und verbinden

### Squeezer (Android)

1. Öffne Squeezer
2. Tippe auf das Menü → **Einstellungen** → **Server**
3. Wähle **Neue Verbindung**
4. Server-Adresse: `192.168.1.100:9000`
5. Verbinden

### Orange Squeeze (Android)

1. Öffne Orange Squeeze
2. Menü → **Preferences** → **Server**
3. **Server address**: IP des Resonance-Servers
4. **Port**: 9000
5. Speichern

### Material Skin (Web-Browser)

Material Skin ist ein Web-Frontend, das direkt im Browser läuft:

```
http://192.168.1.100:9000/
```

> **Hinweis:** Material Skin muss erst in Resonance integriert werden (TODO).

---

## 🧪 Test-Szenarien

### Test 1: Player-Erkennung

**Ziel:** Prüfen, ob die App den Squeezelite-Player sieht.

1. Starte Resonance-Server
2. Starte Squeezelite
3. Öffne die App und verbinde zum Server
4. **Erwartung:** Player erscheint in der Player-Liste

**Prüfen via curl:**

```bash
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d '{"id":1,"method":"slim.request","params":["-",["serverstatus"]]}'
```

### Test 2: Serverstatus abrufen

**Ziel:** Prüfen, ob JSON-RPC funktioniert.

```bash
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d '{"id":1,"method":"slim.request","params":["-",["serverstatus","0","100"]]}'
```

**Erwartete Antwort:**
```json
{
  "id": 1,
  "method": "slim.request",
  "params": ["-", ["serverstatus", "0", "100"]],
  "result": {
    "uuid": "...",
    "version": "0.1.0",
    "player count": 1,
    "players_loop": [...]
  }
}
```

### Test 3: Player-Liste

```bash
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d '{"id":1,"method":"slim.request","params":["-",["players","0","10"]]}'
```

### Test 4: Library-Browse (Artists)

```bash
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d '{"id":1,"method":"slim.request","params":["-",["artists","0","10"]]}'
```

### Test 5: Suche

```bash
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d '{"id":1,"method":"slim.request","params":["-",["search","0","10","term:Beatles"]]}'
```

### Test 6: Playlist Play (Track abspielen)

**Wichtig:** `PLAYER_MAC` durch die MAC-Adresse des Squeezelite ersetzen!

```bash
# Finde die Player-MAC:
curl -s -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d '{"id":1,"method":"slim.request","params":["-",["players","0","10"]]}' | jq '.result.players_loop[0].playerid'

# Track abspielen:
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d '{"id":1,"method":"slim.request","params":["aa:bb:cc:dd:ee:ff",["playlist","play","/path/to/song.mp3"]]}'
```

### Test 7: Playback-Steuerung

```bash
PLAYER="aa:bb:cc:dd:ee:ff"

# Pause
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d "{\"id\":1,\"method\":\"slim.request\",\"params\":[\"$PLAYER\",[\"pause\"]]}"

# Play (Resume)
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d "{\"id\":1,\"method\":\"slim.request\",\"params\":[\"$PLAYER\",[\"play\"]]}"

# Stop
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d "{\"id\":1,\"method\":\"slim.request\",\"params\":[\"$PLAYER\",[\"stop\"]]}"
```

### Test 8: Lautstärke

```bash
PLAYER="aa:bb:cc:dd:ee:ff"

# Lautstärke auf 50%
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d "{\"id\":1,\"method\":\"slim.request\",\"params\":[\"$PLAYER\",[\"mixer\",\"volume\",\"50\"]]}"

# Lautstärke +10
curl -X POST http://localhost:9000/jsonrpc.js \
  -H "Content-Type: application/json" \
  -d "{\"id\":1,\"method\":\"slim.request\",\"params\":[\"$PLAYER\",[\"mixer\",\"volume\",\"+10\"]]}"
```

---

## 🔍 Debugging

### Server-Logs

Der Server gibt detaillierte Logs aus. Achte auf:

- `HELO received` — Squeezelite hat sich verbunden
- `STAT received` — Heartbeat vom Player
- `HTTP request` — Streaming-Anfrage
- `Streaming ...` — Audio wird gesendet

### Netzwerk-Check

```bash
# Prüfe ob Server erreichbar ist
curl http://localhost:9000/health

# Prüfe ob Slimproto-Port offen ist
netstat -an | findstr 3483
```

### Häufige Probleme

| Problem | Lösung |
|---------|--------|
| App findet Server nicht | Prüfe Firewall-Einstellungen für Ports 3483 und 9000 |
| Squeezelite verbindet nicht | Prüfe ob Server läuft, prüfe IP-Adresse |
| Kein Audio | Prüfe Squeezelite Audio-Ausgabe (`-l` für Liste) |
| JSON-RPC timeout | Prüfe ob Server auf Port 9000 läuft |

### Firewall (Windows)

```powershell
# Ports freigeben
netsh advfirewall firewall add rule name="Resonance Slimproto" dir=in action=allow protocol=TCP localport=3483
netsh advfirewall firewall add rule name="Resonance HTTP" dir=in action=allow protocol=TCP localport=9000
```

---

## ✅ Erwartete Ergebnisse

Nach erfolgreichem Test solltest du:

1. ✅ Squeezelite in der App als Player sehen
2. ✅ Library durchsuchen können (Artists, Albums, Tracks)
3. ✅ Tracks zur Playlist hinzufügen können
4. ✅ Playback steuern können (Play, Pause, Stop)
5. ✅ Lautstärke ändern können
6. ✅ Audio über die Lautsprecher hören

---

## 📊 Test-Checkliste

| Test | Status |
|------|--------|
| Server startet ohne Fehler | ⬜ |
| Squeezelite verbindet | ⬜ |
| App verbindet zum Server | ⬜ |
| Player erscheint in App | ⬜ |
| `serverstatus` gibt Daten zurück | ⬜ |
| `players` zeigt Squeezelite | ⬜ |
| `artists` gibt Library-Daten zurück | ⬜ |
| `playlist play` startet Stream | ⬜ |
| Audio kommt aus Lautsprechern | ⬜ |
| `pause` pausiert Playback | ⬜ |
| `mixer volume` ändert Lautstärke | ⬜ |

---

## 🔗 Weiterführende Links

- [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md) — Projekt-Kontext
- [ARCHITECTURE.md](./ARCHITECTURE.md) — System-Architektur
- [SLIMPROTO.md](./SLIMPROTO.md) — Protokoll-Details

---

*Zuletzt aktualisiert: Februar 2026*