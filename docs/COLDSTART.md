# 🚀 Resonance — Coldstart

> **🇩🇪 Antworte IMMER auf Deutsch!**

## Was ist das?

Python-Neuimplementierung des Logitech Media Server (LMS). Server steuert Squeezebox/Squeezelite Player.

## Status

**316 Tests ✅** | ~18.500 LOC Python | ~6.000 LOC Flutter (Cadence)

## Quick Start

```powershell
cd resonance-server
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --verbose
micromamba run -p ".build/mamba/envs/resonance-env" python -m pytest -v
```

## Kritische Regeln

1. **Elapsed-Formel:** `elapsed = start_offset + raw_elapsed`
2. **STMu = Track-Ende**, STMf/STMd = kein State-Change
3. **Seek non-blocking:** `asyncio.create_task()`, sofort antworten
4. **Pause explizit:** `pause 1` / `pause 0` (kein Toggle)
5. **micromamba nutzen**, nicht System-Python

## Pfade

| Was | Pfad |
|-----|------|
| Server | `resonance-server/` |
| Cadence | `C:\Users\stephan\Desktop\cadence` |
| LMS-Referenz | `slimserver-public-9.1/` |

## Nächste Schritte

| Prio | Aufgabe |
|------|---------|
| 🔴 | Multi-Room Sync (Server) |
| 🟡 | Keyboard-Shortcuts (Cadence) |
| 🟡 | Library Search (Cadence) |

## 📚 Dokumentation (bei Bedarf lesen)

| Dokument | Inhalt |
|----------|--------|
| [AI_BOOTSTRAP.md](./AI_BOOTSTRAP.md) | Vollständiger Kontext, Projektstruktur, alle Fallstricke |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System-Architektur, Protokolle, Code-Struktur |
| [SEEK_ELAPSED_FINDINGS.md](./SEEK_ELAPSED_FINDINGS.md) | LMS-konforme Seek/Elapsed Implementierung |
| [SLIMPROTO.md](./SLIMPROTO.md) | Binärprotokoll Details, Message-Format |
| [COMPARISON_LMS.md](./COMPARISON_LMS.md) | Feature-Vergleich mit Original LMS |
| [E2E_TEST_GUIDE.md](./E2E_TEST_GUIDE.md) | Testen mit echten Apps (iPeng, Squeezer) |
| [CHANGELOG.md](./CHANGELOG.md) | Änderungshistorie |
| [ECOSYSTEM.md](./ECOSYSTEM.md) | Squeezebox Hardware/Software Übersicht |

## WHKTM

Bei "whktm" → AI_BOOTSTRAP.md + CHANGELOG.md aktualisieren → "Lies COLDSTART.md und mach weiter"