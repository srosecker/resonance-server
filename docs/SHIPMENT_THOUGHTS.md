# 📦 Resonance — Shipping & Distribution Thoughts

> Überlegungen zur Verteilung und Installation von Resonance

---

## 🎯 Ziel

Resonance soll einfach installierbar sein für:
1. **Python-affine User** → pip install
2. **Server/NAS User** → Docker
3. **Windows Desktop User** → Standalone EXE (kein Python nötig)
4. **Linux Desktop User** → AppImage oder pip

---

## 📜 Lizenz-Situation

### Resonance selbst
- **GPL-2.0** (wie Original-LMS, Community-kompatibel)

### Python Dependencies
| Lizenz | Pakete | GPL-2 kompatibel? |
|--------|--------|-------------------|
| MIT | fastapi, aiosqlite, blurhash, uvicorn, pillow, etc. | ✅ Ja |
| BSD-3 | starlette, numpy, click, etc. | ✅ Ja |
| Apache-2.0 | aiofiles, pytest-asyncio | ✅ Ja |
| GPL-2+ | mutagen | ✅ Ja (gleiche Lizenz!) |
| MPL-2.0 | certifi, pathspec | ✅ Ja |

**Fazit:** Alle Core-Dependencies sind GPL-2 kompatibel ✅

---

## 🔧 Transcoding-Binaries

### Was brauchen wir?

**KEIN ffmpeg!** Resonance nutzt leichtgewichtige, spezialisierte Tools:

| Binary | Wozu | Lizenz | Größe |
|--------|------|--------|-------|
| **faad** | M4A/M4B/AAC dekodieren | GPL-2 | ~200 KB |
| **lame** | MP3 enkodieren | LGPL | ~500 KB |
| **flac** | FLAC dekodieren | BSD | ~400 KB |
| **sox** | Opus/OGG konvertieren | GPL-2 | ~2 MB |

**Total: ~3 MB** vs. ffmpeg mit **~80-150 MB**

### Wann werden sie gebraucht?

| Audio-Format | Transcoding nötig? | Benötigte Tools |
|--------------|-------------------|-----------------|
| MP3 | ❌ Nein (Passthrough) | - |
| FLAC | ❌ Nein (Passthrough) | - |
| OGG Vorbis | ❌ Nein (Passthrough) | - |
| WAV | ❌ Nein (Passthrough) | - |
| M4A/M4B/AAC | ✅ Ja | faad + lame |
| Opus | ✅ Ja | sox |

**Fazit:** Die meisten User (MP3/FLAC/OGG) brauchen KEINE Transcoding-Tools!

---

## 📦 Distributions-Optionen

### 1. pip / PyPI (empfohlen für Python-User)

```bash
pip install resonance
resonance --verbose
```

**Vorteile:**
- Einfachste Distribution
- Automatische Dependency-Auflösung
- Cross-Platform

**Nachteile:**
- User braucht Python 3.11+
- Transcoding-Binaries müssen separat installiert werden

### 2. Docker (empfohlen für Server/NAS)

```bash
docker run -d \
  --name resonance \
  -p 9000:9000 \
  -p 3483:3483 \
  -p 3483:3483/udp \
  -v /path/to/music:/music \
  -v /path/to/config:/config \
  resonance/resonance
```

**Vorteile:**
- Alles enthalten (Python, Dependencies, Binaries)
- Isoliert, keine Konflikte
- Perfekt für Synology, Unraid, Proxmox

**Nachteile:**
- Docker muss installiert sein
- Etwas mehr Overhead

### 3. PyInstaller (Windows EXE / Linux Binary)

```bash
# Windows
resonance.exe --verbose

# Linux
./resonance --verbose
```

**Vorteile:**
- Kein Python nötig
- Einfacher Doppelklick (Windows)
- Kann Transcoding-Binaries bundeln

**Nachteile:**
- Größere Datei (~50-100 MB)
- Build-Prozess für jede Plattform

### 4. System-Pakete (später)

| Plattform | Paketformat | Aufwand |
|-----------|-------------|---------|
| Debian/Ubuntu | .deb / PPA | 🔴 Hoch |
| Arch Linux | AUR | 🟡 Mittel |
| Homebrew (macOS) | Formula | 🟡 Mittel |
| Windows | winget/Scoop | 🟡 Mittel |

---

## 🚀 Empfohlene Rollout-Strategie

### Phase 1: MVP (Jetzt)

1. **GitHub Releases**
   - Source Tarball
   - INSTALL.md mit Anleitungen

2. **pip install** (PyPI)
   ```bash
   pip install resonance
   ```

### Phase 2: Komfortabler

3. **Docker Image**
   ```bash
   docker pull resonance/resonance
   ```

4. **PyInstaller Builds**
   - Windows: `resonance-setup.exe`
   - Linux: `resonance-x86_64.AppImage`

### Phase 3: Breite Verfügbarkeit

5. **System-Pakete** (Community-driven)
   - AUR, Homebrew, etc.

---

## 📝 INSTALL.md Struktur

```markdown
# Installation

## Quick Start (Python User)
pip install resonance
resonance --verbose

## Docker
docker run ...

## Windows (ohne Python)
1. Download resonance-setup.exe
2. Installieren
3. Resonance starten

## Linux (ohne Python)
1. Download resonance.AppImage
2. chmod +x resonance.AppImage
3. ./resonance.AppImage

## Transcoding (optional)
Nur nötig für M4A/M4B/Opus:
- Windows: choco install faad2 lame flac sox
- Linux: apt install faad lame flac sox
- macOS: brew install faad2 lame flac sox
```

---

## ⚠️ Offene Fragen

1. **Transcoding-Binaries bundlen?**
   - Pro: User braucht nichts extra installieren
   - Con: Größeres Paket, Lizenz-Compliance prüfen

2. **Auto-Update Mechanismus?**
   - Für Desktop-User wichtig
   - pip: `pip install --upgrade resonance`
   - Docker: Watchtower o.ä.

3. **Windows Service vs. Tray-App?**
   - Service: Läuft im Hintergrund, startet automatisch
   - Tray: User sieht Status, einfacher Start/Stop

4. **Config-Location?**
   - Linux: `~/.config/resonance/` oder `/etc/resonance/`
   - Windows: `%APPDATA%\Resonance\`
   - Docker: Volume Mount

---

## 🔗 Referenzen

- [PyPI Packaging Guide](https://packaging.python.org/)
- [PyInstaller](https://pyinstaller.org/)
- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [AppImage](https://appimage.org/)