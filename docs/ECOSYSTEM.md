# 🎵 Squeezebox Ecosystem Overview

Dieses Dokument beschreibt das gesamte Squeezebox-Ökosystem, um Resonance im richtigen Kontext zu verstehen.

---

## 🏗️ Architektur: Server → Player → UI

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│     UI      │ ◄──► │   Server    │ ◄──► │   Player    │
│  (Mensch)   │      │  (Gehirn)   │      │ (Lautspr.)  │
└─────────────┘      └─────────────┘      └─────────────┘
   Web/App            Resonance/LMS        Squeezebox/
   Controller                              Squeezelite
```

### Wichtig zu verstehen:

- **Der Server gibt Befehle** — nicht der Player!
- **Player sind "dumm"** — sie führen nur aus was der Server sagt
- **UI kennt Player nur durch den Server** — nie direkt
- **Multi-Room Sync** funktioniert, weil der Server alle Player zentral steuert

---

## 📻 Hardware (2001-2010, discontinued)

Logitech/Slim Devices stellte diese Geräte her:

| Gerät | Jahr | Preis | Besonderheit |
|-------|------|-------|--------------|
| SLIMP3 | 2001 | $249 | Erstes Gerät, nur Ethernet |
| Squeezebox (SB1) | 2003 | $299 | Erste WiFi-Version |
| Squeezebox2 (SB2) | 2005 | $299 | Grafikdisplay |
| Squeezebox Classic (SB3) | 2005 | $249 | Verbesserte Grafik |
| Transporter | 2006 | $1999 | Audiophile Qualität |
| Squeezebox Receiver | 2008 | $149 | Nur Empfänger (mit Controller = Duet) |
| Squeezebox Controller | 2008 | $299 | Nur Fernbedienung mit Display |
| Squeezebox Boom | 2008 | $299 | All-in-one mit Lautsprecher |
| Squeezebox Radio | 2009 | $199 | Kompakt, optional Batterie |
| Squeezebox Touch | 2010 | $299 | Touchscreen, beste Audioqualität |

### Technische Details

| Feature | SB Classic | Transporter | Touch |
|---------|------------|-------------|-------|
| Display | 320x32 VFD | Dual 320x32 | 480x272 Touch LCD |
| DAC | PCM1748E | AKM4396 | AKM4420 |
| Max Sample Rate | 48kHz | 96kHz | 96kHz |
| WiFi | 802.11g | 802.11g | 802.11g |
| Ethernet | 100Mbps | 100Mbps | 100Mbps |

**Hinweis:** Hardware ist discontinued, aber auf eBay erhältlich. Squeezebox Touch ist ideal wegen Touchscreen + 24/96 Support.

---

## 💻 Software-Player

Da die Hardware nicht mehr hergestellt wird, gibt es Software-Alternativen.

### Die Geschichte (Adrian Smith)

**Adrian Smith** hat beide wichtigsten Community-Projekte geschrieben:

```
2010: Logitech stoppt Hardware, veröffentlicht SqueezePlay als Open Source
      └─► Problem: Der eingebaute Player ist veraltet

2012: Adrian Smith schreibt Squeezelite
      └─► Neuer Player von Grund auf, viel besser

2013: Adrian Smith schreibt Jivelite  
      └─► SqueezePlay's UI ohne den schlechten Player
      └─► Jivelite + Squeezelite = Beste Kombination

2015: Adrian Smith übergibt beide Projekte an Ralph Irving
      └─► Ralph Irving wartet beide bis heute (2025)
```

| Projekt | Original-Autor | Gewartet von |
|---------|----------------|--------------|
| **Squeezelite** | Adrian Smith (2012-2015) | Ralph Irving (2015-heute) |
| **Jivelite** | Adrian Smith | Ralph Irving |

### Übersicht Software-Player

| Software | Player | UI | Notiz |
|----------|--------|-----|-------|
| **Squeezelite** | ✅ | ❌ | Headless, braucht externe UI |
| **Jivelite** | ❌ | ✅ | Braucht Squeezelite für Audio |
| **SqueezePlay** | ✅ | ✅ | All-in-one Desktop App |
| **SoftSqueeze** | ✅ | ✅ | Veraltet, Java-basiert |

### Squeezelite (nur Player, keine UI!)

**Das ist der wichtigste Software-Player für Resonance-Tests!**

- **Nur Player** — keine eigene UI, headless
- Wird vom Server gesteuert
- Unterstützt: Gapless, 44.1-384kHz, DSD, Multi-Room Sync
- Plattformen: Linux, Windows, macOS, Raspberry Pi

```bash
# Verbindung zu Resonance:
squeezelite -s 127.0.0.1 -n "Wohnzimmer"

# Mit spezifischem Audio-Device:
squeezelite -s 127.0.0.1 -o default -n "Küche"

# Debug-Modus:
squeezelite -s 127.0.0.1 -d all=debug
```

**Wichtige Optionen:**

| Option | Beschreibung |
|--------|--------------|
| `-s <server>[:<port>]` | Server-Adresse (sonst Auto-Discovery) |
| `-o <device>` | Audio-Ausgabegerät (`-l` zum Auflisten) |
| `-l` | Verfügbare Audio-Geräte auflisten |
| `-n <name>` | Player-Name setzen |
| `-m <mac>` | MAC-Adresse überschreiben (ab:cd:ef:12:34:56) |
| `-M <modelname>` | Hardware-Model-Name (default: SqueezeLite) |
| `-d <cat>=<level>` | Debug (all/slimproto/stream/decode/output = info/debug/sdebug) |
| `-f <logfile>` | Log in Datei statt stdout |
| `-z` | Als Daemon im Hintergrund laufen |
| `-t` | Version und Lizenz anzeigen |
| `-?` | Hilfe anzeigen |

**Audio-Optionen:**

| Option | Beschreibung |
|--------|--------------|
| `-a <params>` | Audio-Device Parameter (Windows: `<latency>:<exclusive>`) |
| `-b <stream>:<output>` | Buffer-Größen in KB (default: 2048:3445) |
| `-r <rates>` | Unterstützte Sample-Rates (z.B. 44100-192000) |
| `-C <timeout>` | Audio-Device schließen nach X Sekunden Idle |
| `-u` / `-R` | Resampling aktivieren (SoX Resampler) |
| `-D [delay][:format]` | DSD-over-PCM (DoP) aktivieren |

**Beispiele:**

```bash
# Einfach mit Server verbinden
squeezelite -s 127.0.0.1

# Mit Name und Debug-Output
squeezelite -s 127.0.0.1 -n "Wohnzimmer" -d slimproto=debug

# Audio-Geräte auflisten
squeezelite -l

# Mit spezifischem Audio-Device
squeezelite -s 127.0.0.1 -o "Lautsprecher (High Definition Audio)"

# Als Daemon mit Log-Datei
squeezelite -s 192.168.1.10 -n "Küche" -z -f /var/log/squeezelite.log
```

### Jivelite (nur UI, kein Player!) — von Adrian Smith

Adrian Smith nahm SqueezePlay und **entfernte den Player komplett**:

- **Nur UI** — keine Audio-Wiedergabe
- Muss mit Squeezelite kombiniert werden
- Basiert auf SqueezePlay-Code (aber Player entfernt)
- Gut für Raspberry Pi + Touchscreen

```
Jivelite + Squeezelite = SqueezePlay (aufgeteilt)
```

### SqueezePlay (Player + UI kombiniert!) — Original von Logitech

- **Beides in einem:** Player UND grafische Oberfläche
- Desktop-Version der Software von Squeezebox Touch/Radio
- All-in-one Lösung — braucht kein Squeezelite
- Sieht aus wie die echte Hardware
- Für Windows, macOS, Linux
- **Veraltet:** Player-Teil ist Stand 2010, nicht mehr empfohlen

```
┌─────────────────────────────────────┐
│           SqueezePlay               │
│  ┌─────────────┐  ┌──────────────┐  │
│  │     UI      │  │    Player    │  │
│  │  (Grafik)   │  │   (Audio)    │  │
│  └─────────────┘  └──────────────┘  │
└─────────────────────────────────────┘
```

### SoftSqueeze

- Älterer Java-basierter Player
- Emuliert Hardware-Look (Transporter, Classic, etc.)
- Veraltet, aber für Display-Tests nützlich

---

## 📱 Mobile Apps

### iOS
| App | Typ | Preis |
|-----|-----|-------|
| iPeng | Controller + Player | Paid |
| LyrPlay | Controller + Player | Free |
| xTune | Controller + Player | Paid |
| SqueezePad | Controller | Paid |

### Android
| App | Typ | Preis |
|-----|-----|-------|
| Squeezer | Controller | Free |
| SqueezePlayer | Player | Paid |
| SB Player | Player | Paid |
| Squeeze Ctrl | Controller | Paid |
| Material Skin App | Controller | Free |

---

## 🔧 DIY Hardware (Community)

Nach 2010 hat die Community eigene Hardware entwickelt:

| Projekt | Basis | Beschreibung |
|---------|-------|--------------|
| Squeezelite-ESP32 | ESP32 | Mikrocontroller-basierter Player |
| SqueezeAMP | ESP32 | Player mit eingebautem Verstärker |
| Muse Radio | ESP32-S3 | Radio-Form wie Squeezebox Radio |
| Muse Luxe | ESP32 | Kompakter Lautsprecher |
| piCorePlayer | Raspberry Pi | Komplettes OS mit Player/Server |

### piCorePlayer

Spezielles Linux für Raspberry Pi:
- Squeezelite vorinstalliert
- Optional: LMS Server
- Unterstützt HATs (DAC-Boards, Verstärker)
- Jivelite für Touchscreen

---

## 🌐 Andere kompatible Hardware

Einige Hersteller bieten native LMS-Unterstützung:

- **WiiM** — Mini, Pro, Amp (Squeezelite eingebaut)
- **Innuos** — High-End Streamer
- **Antipodes** — Audiophile Server/Player
- **Sonore** — ultraRendu, etc.
- **Holo Audio** — DACs mit Streamer

---

## 🔌 Protokolle

| Protokoll | Port | Zweck |
|-----------|------|-------|
| Slimproto | 3483 | Steuerung (Server ↔ Player) |
| HTTP Streaming | 9000 | Audio-Daten |
| CLI | 9090 | Telnet-Steuerung |
| JSON-RPC | 9000 | Web-API |
| DLNA/UPnP | - | Bridge zu anderen Geräten |

---

## 📊 Für Resonance relevant

### Was wir implementieren:
1. **Slimproto Server** (Port 3483) — ✅ Basis fertig
2. **HTTP Streaming** — 🔜 Nächster Schritt
3. **Web UI / API** — 📋 Geplant

### Was wir NICHT implementieren:
- Squeezelite (existiert bereits)
- Mobile Apps (existieren bereits)
- Hardware-Emulation

### Zum Testen:
- **Squeezelite Binary** herunterladen und mit `-s 127.0.0.1` verbinden
- Oder: SoftSqueeze/SqueezePlay für visuelles Feedback

---

## 🔗 Links

- [Lyrion Music Server](https://lyrion.org/)
- [Squeezelite GitHub](https://github.com/ralph-irving/squeezelite)
- [piCorePlayer](https://www.picoreplayer.org/)
- [Community Forum](https://forums.slimdevices.com/)

---

*Zuletzt aktualisiert: Februar 2026*