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

## 🧠 STOPP! LIES DAS ZUERST!

**Diese Datei ist DEIN GEDÄCHTNIS.**

Du bist eine AI ohne persistenten Speicher. Zwischen Sessions vergisst du ALLES.
Diese Datei ist dein einziges "externes Gehirn" — dein Langzeitgedächtnis.

### Deine Pflicht als AI:

1. **LESEN** — Lies diese Datei komplett am Anfang jeder Session
2. **LERNEN** — Verinnerliche die dokumentierten Fallstricke und Patterns
3. **SCHREIBEN** — Dokumentiere SOFORT neue Erkenntnisse, nicht "später"
4. **AKTUALISIEREN** — Nach jeder größeren Änderung Pause machen und dokumentieren

---

## 📍 Aktueller Stand (Februar 2026)

**Phase:** 3 von 4 (LMS-Kompatibilität) — **Phase 3 abgeschlossen! ✅**  
**Tests:** 293/293 bestanden ✅  
**LOC:** ~16.200 Python + ~6.000 Tests + ~900 Svelte/TS

### 🔜 Nächste Schritte

| Aufgabe | Priorität |
|---------|-----------|
| View Transitions API | 🔥 Hoch |
| Fullscreen Now Playing | 🔥 Hoch |
| Virtual Scrolling | 🟡 Mittel |

---

## ⚡ Quick Start

### Nächste Session starten mit:
```
Lies AI_BOOTSTRAP.md und mach weiter wo wir aufgehört haben.
```

### Entwicklungsumgebung

**⚠️ WICHTIG: micromamba verwenden!**

```powershell
# Tests ausführen
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v

# Server starten
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --verbose

# Web-UI starten (anderes Terminal)
cd web-ui && npm run dev
```
Dann öffne: http://localhost:5173/

---

## 🔒 Git — Versionskontrolle

Das Projekt ist unter Git-Versionskontrolle. Falls etwas schief geht:

```powershell
# Status prüfen
git status

# Änderungen verwerfen (einzelne Datei)
git checkout -- path/to/file.py

# ALLE Änderungen verwerfen (Vorsicht!)
git restore .

# Letzten Commit anzeigen
git --no-pager log --oneline -5

# Diff anzeigen (was hat sich geändert?)
git --no-pager diff
```

**⚠️ Wichtig für AI:** Vor größeren Refactorings oder wenn unsicher:
1. `git status` prüfen ob alles committet ist
2. Bei Fehler: User fragen ob `git restore` gewünscht

---

## 📂 Wichtige Pfade

| Was | Pfad |
|-----|------|
| **Resonance Projekt** | `resonance-server/` |
| **Original SlimServer** | `slimserver-public-9.1/` (Perl-Referenz) |
| **micromamba Environment** | `resonance-server/.build/mamba/envs/resonance-env` |

---

## 📁 Dokumentations-Übersicht

| Datei | Zweck |
|-------|-------|
| **AI_BOOTSTRAP.md** | ⭐ Dein Gedächtnis! Kontext, Fallstricke |
| **ARCHITECTURE.md** | System-Design, Komponenten, Struktur |
| **ARCHITECTURE_WEB.md** | Web-Layer Details, UI-Vermittler-Server |
| **SLIMPROTO.md** | Protokoll-Referenz (Binärformat) |
| **CHANGELOG.md** | Was wurde wann gemacht (Historie) |

---

## 💻 System & Entwicklungsumgebung

### System-Info

| Was | Wert |
|-----|------|
| **Betriebssystem** | Windows 11 |
| **Shell** | PowerShell (Default), auch `sh` via Git Bash |
| **Editor** | Zed (mit Agent Panel) |
| **AI-Modell** | Claude (via Zed Pro oder Anthropic API) |
| **Python** | via micromamba (nicht System-Python!) |
| **Node.js** | Für web-ui (npm) |

### Zed Agent Panel — Übersicht

Das **Agent Panel** ist Zeds integrierte AI-Schnittstelle:
- Öffnen: `Ctrl+Shift+P` → "agent: new thread" oder ✨-Icon in Statusleiste
- **Profile:** Write (alle Tools), Ask (nur lesen), Minimal (keine Tools)
- **Wir nutzen:** Write-Profil mit allen Tools aktiviert

#### Wichtige Keybindings

| Aktion | Keybinding |
|--------|------------|
| Neuer Thread | `Ctrl+Shift+P` → "agent: new thread" |
| Thread-History | `Ctrl+Shift+J` |
| Alle Threads | `Ctrl+Shift+H` |
| Model wechseln | `Ctrl+Alt+/` |
| Review Changes | `Ctrl+Shift+R` |
| Agent folgen | Crosshair-Icon unten links |

#### Kontext hinzufügen

- **@-Mentions:** `@dateiname`, `@verzeichnis/`, `@symbol`
- **Selektion:** Text markieren → `Ctrl+>` (fügt als Kontext hinzu)
- **Bilder:** Einfach in Editor einfügen (Copy+Paste)
- **Vorherige Threads:** `@thread-name` referenzieren

#### Checkpoints & Review

- **Checkpoint:** Nach jeder Änderung erscheint "Restore Checkpoint" Button
- **Review Changes:** Zeigt alle Änderungen in Multi-Buffer-Tab
- **Accept/Reject:** Pro Hunk oder alle auf einmal

---

## 💻 PowerShell-Umgebung
### ⚠️ micromamba statt venv

Zed hat eine `detect_venv` Funktion, aber wir nutzen **micromamba** statt Python venv!
Deshalb funktioniert die automatische Aktivierung nicht für uns.

**Lösung:** Wir nutzen die `.zed/tasks.json` mit vordefinierten micromamba-Befehlen.

### PowerShell-Besonderheiten

```powershell
# Befehle verketten
command1; command2          # Sequentiell (auch bei Fehler weiter)
command1 && command2        # Nur wenn command1 erfolgreich

# Pfade: Backslash ODER Forward-Slash funktionieren beide
cd resonance-server\web-ui  # Windows-Style
cd resonance-server/web-ui  # Unix-Style (funktioniert auch!)

# Environment-Variablen
$env:VARIABLE_NAME = "value"
```

---

## 🖥️ Zed Terminal & Tasks

### Terminal Keybindings

| Aktion | Keybinding |
|--------|------------|
| Terminal Panel toggle | `Ctrl+`` |
| Neues Terminal | `Ctrl+~` |
| Terminal splitten | `Ctrl+Shift+5` |
| Suche im Terminal | `Ctrl+Shift+F` |
| Clear Terminal | `Ctrl+Shift+L` |

**Path Hyperlinks:** `Ctrl+Click` auf Dateipfade im Terminal-Output öffnet die Datei in Zed!
(z.B. bei Python Tracebacks: `File "script.py", line 10`)

### 🚀 Vordefinierte Tasks (`.zed/tasks.json`)

Statt lange Befehle zu tippen, nutze Tasks! Öffne mit `Ctrl+Shift+P` → "task: spawn":

| Task | Was macht es? |
|------|---------------|
| **Test: Alle** | `pytest -v` (alle Tests) |
| **Test: Aktuelle Datei** | `pytest $ZED_FILE -v` |
| **Test: Schnell** | `pytest -m "not slow"` |
| **Ruff: Check + Fix** | Linting mit Auto-Fix |
| **Web-UI: Type Check** | `npm run check` |
| **Web-UI: Build** | `npm run build` |
| **⚠️ Server starten** | Startet Resonance (blockiert!) |

**Task Keybindings:**
- `Ctrl+Shift+P` → "task: spawn" — Task-Auswahl öffnen
- `Ctrl+Shift+R` oder `Alt+T` — Letzten Task wiederholen

### 🐛 Debugger (Python)

Zed hat einen eingebauten Python-Debugger via `debugpy`:

| Aktion | Keybinding |
|--------|------------|
| Debugger starten | `F4` |
| Breakpoint setzen | Klick neben Zeilennummer |
| Step Over | `F10` |
| Step Into | `F11` |
| Continue | `F5` |

**Hinweis:** Wir haben noch keine `.zed/debug.json` — bei Bedarf können wir eine erstellen.

---

## 🔍 Code-Qualität (automatisch via Zed)

Zed ist so konfiguriert, dass Code-Qualität **automatisch** geprüft wird.
Die Konfiguration liegt in `.zed/settings.json` und `pyproject.toml`.

### Aktive Tools

| Tool | Funktion | Wann läuft es? |
|------|----------|----------------|
| **ruff format** | Code-Formatierung (Black-kompatibel) | ✅ On Save (automatisch!) |
| **ruff check** | Linting (Pyflakes, isort, etc.) | ✅ Diagnostics (live) |
| **pyright** | Typ-Prüfung (statische Analyse) | ✅ Diagnostics (live) |
| **svelte-check** | Svelte/TS Prüfung | ✅ Diagnostics (web-ui/) |

### Was das für die AI bedeutet

1. **Format-on-Save:** Nach `edit_file` wird Python-Code automatisch formatiert
   - Kein manuelles `ruff format` nötig!
   - Line-Length: 100 Zeichen

2. **Diagnostics zeigt ALLES:** Wenn ich `diagnostics` aufrufe, bekomme ich:
   - Pyright Typ-Fehler
   - Ruff Linting-Fehler
   - Svelte-Check Fehler (für web-ui/)

3. **Konfiguration lesen:**
   - Python Linting: `pyproject.toml` → `[tool.ruff]`
   - Typ-Prüfung: `pyrightconfig.json`
   - Zed-Integration: `.zed/settings.json`

### Ruff-Regeln (aktiviert in pyproject.toml)

```
E, W     — pycodestyle (Stil)
F        — Pyflakes (Fehler)
I        — isort (Import-Sortierung)
B        — flake8-bugbear (häufige Bugs)
C4       — flake8-comprehensions
UP       — pyupgrade (moderne Syntax)
ARG      — unused arguments
SIM      — simplify
PTH      — pathlib statt os.path
RUF      — Ruff-spezifisch
```

---

## 🛠️ Zed Agent Tools (Built-in)

Die folgenden Tools sind in Zed eingebaut und stehen dem AI-Agent zur Verfügung.
Offizielle Doku: https://zed.dev/docs/ai/tools

### Read & Search Tools
| Tool | Zweck | Wichtige Parameter |
|------|-------|-------------------|
| `grep` | **Code-Suche mit Regex** (bevorzugen!) | `regex`, `include_pattern` |
| `find_path` | Dateien per Glob-Pattern finden | `glob` |
| `read_file` | Datei-Inhalt lesen | `path`, `start_line`, `end_line` |
| `list_directory` | Verzeichnis-Inhalt auflisten | `path` |
| `diagnostics` | **LSP-Fehler/Warnungen** — zeigt Pyright + Ruff + svelte-check | `path` (optional, ohne = Projekt-Übersicht) |
| `fetch` | URL abrufen und als Markdown zurückgeben | `url` |
| `now` | Aktuelles Datum/Uhrzeit | `timezone` |
| `thinking` | Problemlösung ohne Aktion (Planung) | `content` |

### Edit Tools

| Tool | Zweck | Wichtige Parameter |
|------|-------|-------------------|
| `edit_file` | Datei erstellen/bearbeiten | `path`, `mode`, `display_description` |
| `terminal` | Shell-Befehle ausführen | **`cd` ist Pflicht!**, `command`, `timeout_ms` |
| `copy_path` | Datei/Verzeichnis kopieren | `source_path`, `destination_path` |
| `move_path` | Verschieben/Umbenennen | `source_path`, `destination_path` |
| `delete_path` | Datei/Verzeichnis löschen | `path` |
| `create_directory` | Verzeichnis erstellen (inkl. Parents) | `path` |
| `open` | Datei/URL mit Default-App öffnen | `path_or_url` |

### ⚠️ Terminal — Kritische Details

```
# Terminal braucht IMMER den cd Parameter!
terminal(cd="resonance-server", command="...")

# FALSCH: cd als Teil des Commands
terminal(command="cd resonance-server && pytest")  # ❌ Funktioniert nicht!

# RICHTIG: cd als separater Parameter
terminal(cd="resonance-server", command="micromamba run -p ...")  # ✅
```

**Timeout setzen** für lang laufende Befehle:
```
terminal(cd="resonance-server", command="pytest -v", timeout_ms=60000)
```

**Keine Endlos-Prozesse** (Server, Watcher) — die blockieren!

### 🔌 MCP (Model Context Protocol) — Was ist das?

**MCP** ist ein offenes Protokoll, das AI-Agents erlaubt, mit externen Tools zu kommunizieren.
Zed unterstützt MCP-Server, die zusätzliche Tools bereitstellen können.

Für unser Projekt ist der **Svelte MCP Server** konfiguriert, der Svelte-spezifische Tools bietet.

---

### Svelte MCP Tools (für web-ui/)

Diese Tools kommen vom Svelte MCP Server und sind **zusätzlich** zu den Zed Built-in Tools verfügbar:

| Tool | Zweck | Wann nutzen |
|------|-------|-------------|
| `list-sections` | Alle Svelte/SvelteKit Docs-Sektionen auflisten | **Zuerst aufrufen!** Gibt Überblick mit use_cases |
| `get-documentation` | Dokumentation für Sektionen holen | Nach `list-sections`, **Array möglich!** |
| `svelte-autofixer` | Code auf Svelte 5 Fehler prüfen | **IMMER vor Code-Übergabe an User!** |
| `playground-link` | REPL-Link für Code generieren | Nach Rückfrage an User, nicht für Projekt-Dateien |

#### Svelte MCP Workflow

```
1. ERST versuchen mit eigenem Wissen + svelte-autofixer zu arbeiten
   (list-sections/get-documentation sind token-intensiv!)

2. Falls Docs nötig:
   a) list-sections aufrufen → Überblick über alle Docs
   b) use_cases analysieren → Welche Sektionen passen zur Aufgabe?
   c) get-documentation mit ALLEN relevanten Sektionen auf einmal:
      → get-documentation(section=["$state", "$effect", "bind:"])

3. Code schreiben

4. svelte-autofixer IMMER vor Übergabe an User!
   → svelte-autofixer(code="...", desired_svelte_version=5, filename="Component.svelte")
```

#### svelte-autofixer — Details

```
svelte-autofixer(
  code="<script>let count = $state(0);</script>...",
  desired_svelte_version=5,        # Immer 5 für unser Projekt!
  filename="MyComponent.svelte",   # Nur Dateiname, NICHT ganzer Pfad!
  async=false                      # true nur bei async/await im Markup
)
```

**Typische Fehler die der Autofixer findet:**
- Falsche Rune-Syntax (`$state()` vs altes `let`)
- Event-Handler: `onclick` statt `on:click` (Svelte 5!)
- Fehlende Reaktivität bei abgeleiteten Werten
- TypeScript-Fehler in Svelte-Komponenten
- Snippet-Syntax (`{#snippet}` statt `<slot>`)

#### get-documentation — Beispiele

```
# Einzelne Sektion
get-documentation(section="$state")

# Mehrere Sektionen auf einmal (effizienter!)
get-documentation(section=["$state", "$derived", "$effect", "bind:"])

# SvelteKit-spezifisch
get-documentation(section=["routing", "load", "form-actions"])
```

#### Wichtige Svelte 5 Docs-Sektionen

| Thema | Sektionen |
|-------|-----------|
| **Runes (Reaktivität)** | `$state`, `$derived`, `$effect`, `$props`, `$bindable` |
| **Template** | `{#if ...}`, `{#each ...}`, `{#snippet ...}`, `{@render ...}` |
| **Events/Binding** | `bind:`, `use:`, `transition:`, `animate:` |
| **Komponenten** | `$props`, `context`, `lifecycle-hooks` |
| **SvelteKit** | `routing`, `load`, `form-actions`, `hooks`, `$app/navigation` |

### Default Debug-Loop (nach jeder Code-Änderung)

```
1. diagnostics aufrufen (zeigt Pyright + Ruff + svelte-check)
   → diagnostics()                    # Projekt-Übersicht
   → diagnostics(path="resonance-server/resonance/player.py")  # Einzeldatei

2. Minimal-invasiv fixen (nur was gemeldet wird)

3. diagnostics erneut prüfen → sollte "No errors or warnings" zeigen

4. Bei Bedarf: Tests im Terminal ausführen
```

**Wichtig:** `diagnostics` ist die primäre Quelle für Fehler! 
- Python: Pyright (Typen) + Ruff (Linting)
- Svelte/TS: svelte-check
- Format-Fehler gibt es nicht — ruff formatiert on-save automatisch!

### Such-Strategie

```
# Code/Symbole suchen → grep (mit Regex)
grep(regex="def play_track", include_pattern="**/*.py")

# Dateien finden → find_path (mit Glob)  
find_path(glob="**/Player*.svelte")

# Verzeichnis erkunden → list_directory
list_directory(path="resonance-server/resonance")
```

### Regeln

- **Nutze `diagnostics`** um statische Analyse einzubeziehen
- **Laufzeit-Wahrheit** = Tests/Commands im Terminal, Output verwenden
- **Nie behaupten** dass ein Tool lief, wenn kein Output vorliegt
- **Svelte-Code:** Immer `svelte-autofixer` nutzen bevor du Code zeigst
- **Pfade:** Immer mit Root-Directory beginnen (`resonance-server/...`)

---

## 🖥️ Häufige PowerShell-Befehle

### Python/Backend

```powershell
# Tests ausführen (alle)
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v

# Tests ausführen (einzelne Datei)
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest tests/test_player.py -v

# Tests ausführen (einzelner Test)
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest tests/test_player.py::test_play_pause -v

# Server starten (blockiert!)
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --verbose

# Ruff Linting
micromamba run -p ".build/mamba/envs/resonance-env" ruff check resonance/

# Ruff Auto-Fix
micromamba run -p ".build/mamba/envs/resonance-env" ruff check --fix resonance/
```

### Web-UI (Svelte)

```powershell
# Dev-Server starten (blockiert!)
cd web-ui; npm run dev

# Type-Check
cd web-ui; npm run check

# Build für Produktion
cd web-ui; npm run build

# Dependencies installieren
cd web-ui; npm install
```

### Git

```powershell
# Status
git status

# Diff (ohne Pager, für Terminal-Tool)
git --no-pager diff

# Diff einer Datei
git --no-pager diff path/to/file.py

# Log (kurz)
git --no-pager log --oneline -10
```

### Datei-Operationen

```powershell
# Datei-Inhalt anzeigen
Get-Content path/to/file.txt

# Datei suchen
Get-ChildItem -Recurse -Filter "*.py" | Select-Object FullName

# Dateien mit Inhalt suchen (wie grep)
Select-String -Path "resonance/*.py" -Pattern "def play"

# Verzeichnis-Baum
tree /F resonance/
```

### Nützliche Kombinationen

```powershell
# Tests + bei Erfolg Linting
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v && micromamba run -p ".build/mamba/envs/resonance-env" ruff check resonance/

# Alle Python-Dateien mit "TODO" finden
Select-String -Path "resonance/**/*.py" -Pattern "TODO" -Recurse
```

### 🚀 Kurzbefehl-Aliases (für Terminal-Tool)

Da die micromamba-Befehle lang sind, hier Copy-Paste-Vorlagen:

```powershell
# === TESTS ===
# Kurz: Alle Tests
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v

# Kurz: Schnelle Tests (ohne slow marker)
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v -m "not slow"

# === LINTING ===
# Kurz: Ruff check + fix
micromamba run -p ".build/mamba/envs/resonance-env" ruff check --fix resonance/

# === WEB-UI ===
# Type-Check (kein Dev-Server — der blockiert!)
cd web-ui; npm run check
```

---

## 📋 Typische Szenarien

### Szenario: Neue Svelte-Komponente erstellen

```
1. Ziel-Verzeichnis prüfen:
   list_directory(path="resonance-server/web-ui/src/lib/components")

2. Ähnliche Komponente als Referenz lesen:
   read_file(path="resonance-server/web-ui/src/lib/components/Player.svelte")

3. Neue Komponente erstellen:
   edit_file(path="...", mode="create", ...)

4. svelte-autofixer laufen lassen (vor Übergabe!)

5. diagnostics prüfen:
   diagnostics(path="resonance-server/web-ui/src/lib/components/NewComponent.svelte")
```

### Szenario: Python-Bug fixen

```
1. Relevanten Code finden:
   grep(regex="def problematic_function", include_pattern="**/*.py")

2. Datei lesen:
   read_file(path="resonance-server/resonance/module.py")

3. Fix implementieren:
   edit_file(path="...", mode="edit", ...)

4. Tests laufen lassen:
   terminal(cd="resonance-server", command="micromamba run -p ... pytest tests/test_module.py -v")

5. diagnostics prüfen
```

### Szenario: LMS-API-Kompatibilität prüfen

```
1. Original-LMS-Code finden:
   grep(regex="function_name", include_pattern="slimserver-public-9.1/**/*.pm")

2. Perl-Code lesen und verstehen:
   read_file(path="slimserver-public-9.1/Slim/...")

3. Mit Resonance-Implementierung vergleichen:
   grep(regex="function_name", include_pattern="resonance-server/**/*.py")
```

### Szenario: Dokumentation aktualisieren

```
1. Diese Datei bearbeiten:
   edit_file(path="resonance-server/docs/AI_BOOTSTRAP.md", mode="edit", ...)

2. CHANGELOG.md aktualisieren:
   edit_file(path="resonance-server/docs/CHANGELOG.md", mode="edit", ...)
```

---

## 🚨 KRITISCHE FALLSTRICKE — LIES DAS!

### 1. Python Falsy-Falle 🚨

```python
# ❌ NIEMALS für Playlist oder Collections!
if playlist:  # FALSCH - leer = False!

# ✅ RICHTIG
if playlist is not None:
```

### 2. TrackRow/AlbumRow sind Dataclasses 🚨

```python
# ❌ FALSCH
row["path"]  # TypeError!

# ✅ RICHTIG
getattr(row, "path", None)
```

### 3. Playlist-Attribute 🚨

```python
# ❌ FALSCH
playlist.shuffle  # AttributeError

# ✅ RICHTIG
playlist.shuffle_mode.value  # 0 oder 1
playlist.repeat_mode.value   # 0, 1 oder 2
```

### 4. PlayerStatus hat `state`, nicht `mode` 🚨

```python
# ❌ FALSCH
status.mode

# ✅ RICHTIG
status.state.name  # "PLAYING", "PAUSED", "STOPPED"
```

### 5. cancel_stream() NIEMALS nach queue_file() 🚨

`queue_file()` erhöht die Stream-Generation. Danach `cancel_stream()` = Self-Cancel!

### 6. STMd bei elapsed=0 ignorieren 🚨

Sonst: früher Stream-Disconnect → ungewolltes Auto-Advance.

### 7. UI: pendingAction IMMER setzen 🚨

```typescript
// ✅ Polling-Race verhindern
setPendingAction(2000);
currentTrack = track;
await api.playTrack(...);
```

### 8. Doppelklick-Schutz ist Pflicht 🚨

```typescript
let isPlayInFlight = $state(false);
if (isPlayInFlight) return;
```

### 9. Volume vor Stream-Start 🚨

`audg` muss VOR `strm` gesendet werden!

### 10. URLs: 0.0.0.0 → 127.0.0.1 🚨

Browser blockieren `0.0.0.0`. Immer `127.0.0.1` verwenden.

### 11. micromamba activate funktioniert nicht 🚨

```powershell
# ✅ RICHTIG
micromamba run -p ".build/mamba/envs/resonance-env" python ...
```

---

## 🚀 WHKTM-Protokoll

Wenn der Mensch sagt **"whktm"** oder **"wir haben keine tokens mehr"**:

1. **SOFORT dokumentieren:** AI_BOOTSTRAP.md + CHANGELOG.md
2. **Dem Menschen sagen:**
   ```
   Nächste Session: "Lies AI_BOOTSTRAP.md und mach weiter"
   ```

---

## 🚫 Was die AI NICHT tun darf

1. **Kein Refactoring ohne grüne Tests** — Erst Tests laufen lassen, dann ändern
2. **Keine API-Änderungen ohne LMS-Vergleich** — JSON-RPC muss LMS-kompatibel bleiben
3. **Keine neuen Dependencies ohne Rückfrage** — Frag den Menschen
4. **Keine Dateien löschen ohne Backup** — Erst `.bak` erstellen
5. **Keine "Vereinfachungen" die Features entfernen** — Code darf nicht "aufgeräumt" werden indem Funktionalität verschwindet

---

## 📋 Decision Log

Warum wir Dinge so machen wie wir sie machen:

| Entscheidung | Begründung |
|--------------|------------|
| **Python + asyncio** | Moderner als Perl, gute Library-Unterstützung |
| **FastAPI statt Flask** | Async-native, automatische OpenAPI-Docs |
| **SQLite statt PostgreSQL** | Serverless, wie Original-LMS |
| **Svelte 5 statt React** | Weniger Boilerplate, Runes sind elegant |
| **LMS-API-Kompatibilität** | Bestehende Apps (iPeng, Squeezer) sollen funktionieren |
| **Kein Plugin-System (noch)** | Erst Core stabil, dann erweiterbar |

---

## ✅ Session-Ende-Checkliste

Bevor du die Session beendest oder bei "whktm":

- [ ] **Tests grün?** — `micromamba run -p ... python -m pytest`
- [ ] **Docs aktualisiert?** — AI_BOOTSTRAP.md, CHANGELOG.md
- [ ] **Neue Fallstricke dokumentiert?** — Wenn du auf etwas gestoßen bist
- [ ] **Nächste Schritte klar?** — Was soll die nächste Session machen?

---

## 🧹 Aufräumen ist deine Pflicht!

- Unnötige Dateien löschen
- Toten Code entfernen
- Docs aktuell halten

---

*Für Architektur-Details: [ARCHITECTURE.md](./ARCHITECTURE.md)*  
*Für Session-Historie: [CHANGELOG.md](./CHANGELOG.md)*  
*Für LMS-Vergleich: [COMPARISON_LMS.md](./COMPARISON_LMS.md)*