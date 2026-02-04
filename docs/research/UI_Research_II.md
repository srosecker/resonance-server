# Deep Research (2026): Das ultimative Web-Interface für **Resonance**

> Ziel: Ein Web-Interface, das nicht nur „LMS-kompatibel“ ist, sondern **Design‑Referenz** für Self‑Hosted Music wird: schnell, warm, hochwertig, multiroom‑fähig, keyboard‑stark, und mit echten *Wow‑Momenten*.

---

## 0) Executive Summary

**Empfohlene Richtung:** *„Vinyl‑warm trifft Spotify‑clean“*  
- **Clean & modern** (hohe Lesbarkeit, klare Hierarchie, wenig Chrome)  
- **Wärme & Charakter** über Album‑Art‑basierte Akzente (adaptive Farben), haptische Micro‑Interactions und „Analog“-Details (VU‑Meter‑Optional, sanfte Texturen, subtiler Glow).  
- **App‑Feeling** via nativen Transition‑Patterns (View Transition API) + flüssigem Now‑Playing, ohne Heavy‑Animations.

**Tech‑Kern:**  
- Frontend: **Svelte 5 + SvelteKit** (beste Passung für „lokaler Musikserver“: schnell, geringe Overhead, SSR optional) – Svelte 5 ist stabil (seit Okt 2024).  
- Realtime: **WebSocket/SSE** *oder* euer bestehendes **CometD/Bayeux** weiter nutzen; wichtig ist **zeitbasierte Glättung** für Positionsupdates.  
- Performance: Virtualisierung bei Library/Queues, aggressive Bild‑Strategie (BlurHash + LQIP), Caching von Album Art via Cache Storage.

---

## 1) Design & Ästhetik (2026)

### 1.1 Visuelle Identität: „Modern, aber nicht klinisch“
**Warum das funktioniert:** Musik wird oft lange Sessions genutzt (Wohnzimmer, Tablet an der Wand). Das UI muss *entspannend* sein, nicht „Dashboard‑Stress“.

**Stil‑Bausteine**
- **Typo:** 2–3 Gewichtungen, starke Headline für Album/Track, ruhige Secondary‑Textfarbe.
- **Layout:** große „Hero“-Now‑Playing Fläche, daneben modulare Panels (Queue, Lyrics, Geräte).
- **Materialität:** Soft‑Shadows + Glas/Blur sparsam, weil Album Art schon „laut“ ist.
- **Motion:** *80% subtil* (Hover, Press, Fokuswechsel), *20% showy* (Transitions, Now‑Playing).

### 1.2 Album Art als Design-Engine
**Ziel:** Cover Art dominiert, aber UI bleibt „geordnet“.

**Best Practices**
- **Adaptive Akzentfarbe** pro Album/Artist: Palette aus Cover extrahieren (z.B. `node-vibrant`) und **nur** für Akzente nutzen (Buttons, Slider‑Fill, Active‑States).  
  - Empfehlung: Palette **serverseitig** oder in einem **Worker** berechnen und cachen (sonst UI‑Jank).  
  - `node-vibrant` ist Worker‑tauglich und weit verbreitet.  
- **Blur/Glass**: Blur auf *Hintergrundebene* (Hero), nicht auf Texte.  
- **Chaos vermeiden**: Album Art auf 1–2 Flächen begrenzen (Hero + Mini‑Covers in Listen).

**Placeholders**
- **BlurHash** als super‑kompakter Placeholder (20–30 Zeichen), erzeugt serverseitig, im Client decodieren → wirkt „edel“ und reduziert wahrgenommene Ladezeit.

**Quellen**
- Svelte 5 Stabilität: https://svelte.dev/blog/svelte-5-is-alive  
- node-vibrant Guides: https://vibrant.dev/guides/get-started/  
- BlurHash Repo: https://github.com/woltapp/blurhash  
- BlurHash Praxisartikel: https://uploadcare.com/blog/blurhash-images/

### 1.3 Animationen & Micro-Interactions
**2026 „State of the Art“ (im Web)**
- **Native View Transitions** für SPA‑Navigation: vermittelt Kontext, fühlt sich wie App an.  
- **Progress/Seek**: keine „springenden“ Werte; immer zeitbasierte Interpolation.
- **Micro‑Interactions**:
  - Press‑Feedback (Scale 0.98), Fokus‑Ring für Keyboard‑Navigation
  - Mini‑Queue‑Reorder mit Magnet‑Feedback
  - „Add to Queue“ Toast: klein, nicht nervig

**Quellen**
- View Transitions (SPAs): https://web.dev/learn/css/view-transitions-spas  
- MDN View Transition API: https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API  
- Chrome 2025 Update: https://developer.chrome.com/blog/view-transitions-in-2025

---

## 2) UX: Informationsarchitektur & Kern-Flows

### 2.1 Navigation für 50.000+ Tracks
**Empfohlenes Modell:**
- **Left Sidebar**: Library, Search, Queue, Radios/Mixes, Playlists, Devices
- **Top Bar**: Search (immer verfügbar), Breadcrumb/Filter (Focus), Quick Actions
- **Now Playing**: persistent als Bottom Bar + optional Fullscreen/Hero

**Browse vs. Search**
- **Casual**: Search first + „Top Artists/Recently Added“
- **Power‑User**: Browse + Filter (Focus‑ähnlich) + Keyboard‑Shortcuts

**Feature: „Focus“ (Multi-Filter)**
- Filterchips: Genre, Year, Label, Format, Sample Rate, Rating, Tags, „Recently Played“, „Not Played“
- Das ist *Roon‑ähnlich* und extrem sticky.

### 2.2 Now Playing Experience (das Herzstück)
**Drei Ebenen**
1. **Mini Player** (bottom): Play/Pause, Skip, Progress, Output/Devices, Lautstärke
2. **Expanded** (panel): Queue + Next Up + Lyrics + Track Info
3. **Fullscreen** (Hero): großes Cover, Mood‑Visualisierung optional (spectrum/vu), „Session‑Mode“

**Welche Metadaten zeigen?**
- **Default:** Codec, Bitrate, Sample Rate (kompakt, ausklappbar)
- **Audiophile Mode:** zusätzl. Bit‑Depth, Output Path, ReplayGain, Gapless Status

### 2.3 Multi-Room / Multi-Player (5+ Player)
**UI‑Pattern:** „Devices Drawer“
- Liste/Grids der Player mit Status (playing/paused/idle), Cover‑Mini, Volume‑Slider
- **Sync‑Gruppen** als „Stack“: Gruppe hat Master‑Volume + expandierbare Mitglieder
- One‑tap „Move playback“ (Queue + Position) zwischen Playern

### 2.4 Touch + Desktop (Tablet an der Wand UND Desktop)
- Touch: große Targets (min. ~44px), Swipe‑Gesten für Queue/Skip optional
- Desktop: Dichte‑Regler („Compact / Comfortable / Cozy“)
- „TV / 10‑Foot Mode“: extrem große Typo, minimaler Text, Fokus auf Cover & Controls

---

## 3) Technische Architektur (2026)

### 3.1 Framework: Empfehlung und Begründung

**Empfehlung: Svelte 5 + SvelteKit**
- Svelte 5 ist stabil (Okt 2024) und bringt „Runes“ + Compiler‑Verbesserungen → kleinere Bundles, gute Reaktivität.  
- SvelteKit eignet sich gut für lokale Server‑UIs: SSR/MPA‑Patterns optional, Routing/Prefetching out of the box.

**Alternativen**
- **React 19**: starke Ecosystem‑Power, Server Actions/Components (wenn ihr später Cloud‑Features baut).  
- **Vue**: Vapor Mode‑Roadmap zielt auf Performance‑Boost.  
- **Solid**: sehr schnell, 2.0 in Arbeit – aber Ökosystem/Team‑Familiarity abwägen.

**Quellen**
- Svelte 5 „alive“: https://svelte.dev/blog/svelte-5-is-alive  
- „Runes“ Hintergrund: https://svelte.dev/blog/runes  
- React 19: https://react.dev/blog/2024/12/05/react-19  
- Vue Vapor Roadmap Issue: https://github.com/vuejs/core/issues/13687  
- Solid 2.0 Roadmap Discussion: https://github.com/solidjs/solid/discussions/2425

### 3.2 Real-Time Updates: Smooth, nicht „zitterig“
**Ziel:** Positionsupdates fühlen sich „analog“ smooth an.

**Pattern**
- Server sendet Position z.B. alle 250–500ms (oder bei Drift)
- Client: **interpoliert** Position anhand `performance.now()` + last known position + playbackRate
- Bei Drift > X ms: soft snap (ease‑out), nicht hart springen

**Transport**
- WebSocket: am direktesten  
- SSE: gut für einseitige Updates  
- **CometD/Bayeux**: behalten, wenn’s schon sitzt; wichtig ist Client‑Glättung (Transport ist zweitrangig).

### 3.3 Offline/PWA
**Ja, aber pragmatisch**
- „Offline“ heißt hier: UI lädt auch ohne Internet (im Heimnetz).  
- Cache: Shell + Icons + zuletzt genutzte Album Art + zuletzt genutzte Views.

**Storage**
- Cache Storage/IndexedDB sind überall verfügbar (web.dev Empfehlung).  
- Album Art: Cache‑Key pro `imageId+size` und LRU‑Eviction.

**Quellen**
- Storage Empfehlungen: https://web.dev/articles/storage-for-the-web  
- Service Worker Best Practices: https://dev.to/austinwdigital/intro-to-service-workers-best-practices-threat-mitigation-59a3

### 3.4 Performance: harte Budgets
**Zielwerte (lokales LAN, Desktop/Tablet)**
- App Shell First Paint: **< 1.0s**  
- Interaktion nach Navigation: **< 100ms** gefühlt (kein Input‑Lag)  
- Scroll in Library/Queue: **60fps** stabil  
- Album Art: LQIP sofort, HQ nachladen ohne Layout Shift

**Techniken**
- **Virtualisierung**: Artist/Album/Track Listen + Queue (TanStack Virtual o.ä.)  
- **IntersectionObserver** fürs Lazy‑Loading  
- **BlurHash** Placeholders  
- **OffscreenCanvas**/Worker für Visualisierungen & Farbextraktion

**Quellen**
- Virtualisierung (web.dev): https://web.dev/articles/virtualize-long-lists-react-window  
- OffscreenCanvas (web.dev): https://web.dev/articles/offscreen-canvas  
- MDN OffscreenCanvas: https://developer.mozilla.org/en-US/docs/Web/API/OffscreenCanvas

---

## 4) Killer-Features (Differenzierung)

### 4.1 „Sonic“ Features wie Plexamp – aber lokal & offen
**Was Nutzer lieben**
- „Sonic analysis“: ähnliche Tracks/Artists, Track Radio, Mix‑Vorschläge.

**Resonance‑Ansatz**
- Optionaler Background‑Job: Audio‑Features (z.B. Loudness, Tempo, Timbre‑Embeddings)  
- Features:
  - „Track Radio“ (ähnliche Songs)
  - „Album‑Journey“ (albumweise ähnliche Alben)
  - „Sweet Fades“ / MixRamp‑ähnliche Crossfades (vorsichtig, Album‑Mode disable)

**Quelle**
- Plex Sonic Analysis Beschreibung: https://support.plex.tv/articles/sonic-analysis-music/

### 4.2 Discovery, aber nicht Roon‑teuer
**UI‑Killer**: „Entdecken“ ist ein eigener Tab, nicht nur „Suche“.
- Daily Mixes (6 Themes)
- Random Album mit Kontext („Warum dieses Album?“)
- Smart Playlists (Regel‑Builder: Genre+Year+NotPlayed+Rating)

**Quelle**
- Roon Discovery / Daily Mixes: https://roon.app/en/music/discovery  
- Roon „Focus“ für Filter: https://roon.app/en/pro

### 4.3 Keyboard‑First (Power‑User Magnet)
- Global Command Palette (⌘K): play, enqueue, add tag, jump to artist…
- Vim‑ähnliche Shortcuts optional
- Focus‑Management (A11y): super sauberer Tab‑Flow

### 4.4 Customization, aber „safe“
- Widgets: Now Playing, Queue, Devices, Discovery, Stats
- Themes: 3–5 hochwertige Presets + „Auto (Album Art)“

---

## 5) Zielgruppen-Analyse: Personas & Erwartungen

### 5.1 Heutige LMS-Nutzer
- Audiophile mit FLAC‑Sammlung, Multiroom
- Self‑Hoster / Home Automation
- Legacy‑Squeezebox Besitzer  
**Hinweis:** Material Skin ist heute ein beliebter moderner UI‑Ersatz.

**Quellen**
- Material Skin Repo: https://github.com/CDrummond/lms-material  
- Lyrion (LMS) Übersicht: https://en.wikipedia.org/wiki/Lyrion_Music_Server

### 5.2 Neue Zielgruppen
- „Spotify‑Flüchtlinge“ (Ownership/Privacy)
- Design‑bewusste Nutzer (wollen schöne Software)
- Hi‑Res Käufer (Qobuz etc.)
- „Ich hab wieder MP3s“ Nostalgie

### 5.3 Erwartungen nach Segment
- Techniker: API, Logs, Debug‑Overlay, Export/Import
- Casual: „Instant“, klare Defaults, weniger Optionen
- Audiophile: Signal‑Pfad, Bit‑Perfect, Gapless
- Designer: Konsistenz, Motion‑System, hochwertige Typo

---

## 6) Benchmarks & Inspiration (transferierbare Patterns)

### Musik-Apps (UIs)
- Spotify: Navigation/Discover/Queue Patterns
- Apple Music: Typo, Album‑First, Lyrics
- Plexamp: Sonic features, „Radio“, Fades

### Self-hosted Referenzen
- Navidrome: moderne Web UI (React + Material UI) und „funktioniert einfach“  
  Quelle: https://www.navidrome.org/docs/overview/

### Außerhalb Musik
- Gaming: Steam Deck / Console UIs → 10‑Foot Mode & Fokus‑Navigation
- Smart Home: Home Assistant → „Panels“/Dashboards & Touch‑Optimierung

---

## 7) Feature-Matrix (kompakt)

| Bereich | Resonance (Ziel) | LMS Default | Material Skin | Plexamp | Roon |
|---|---|---|---|---|---|
| Modernes Design | ✅ Premium | ❌ legacy | ✅ modern | ✅ sehr gut | ✅ sehr gut |
| Multiroom & Sync | ✅ Kern | ✅ | ✅ | ⚠️ je nach Setup | ✅ Kern |
| Discovery / Radio | ✅ lokal, offen | ⚠️ basic | ⚠️ | ✅ sonic | ✅ stark |
| Focus / Multi-Filter | ✅ Roon‑ähnlich | ❌ | ⚠️ | ⚠️ | ✅ |
| Keyboard‑First | ✅ | ❌ | ⚠️ | ⚠️ | ⚠️ |
| PWA / Tablet Mode | ✅ | ❌ | ✅ | ✅ App | ✅ |
| Audiophile Details | ✅ optional | ✅ | ✅ | ⚠️ | ✅ |

---

## 8) Empfohlener Tech-Stack (konkret)

### Frontend
- **Svelte 5 + SvelteKit**
- Styling: **Tailwind CSS v4** (perf & modern), plus Design‑Tokens  
  Quelle: https://tailwindcss.com/blog/tailwindcss-v4
- State: Svelte Stores + Query Layer (fetch/invalidations), optional TanStack Query

### Daten & Realtime
- APIs: JSON‑RPC (LMS kompatibel) + REST
- Realtime: CometD weiter nutzen **oder** WS/SSE; wichtig ist Smooth‑Interpolation

### Media Assets
- Album Art Endpoints: `?size=64/128/256/512/1024&format=webp/avif`
- Placeholders: BlurHash
- Farbpalette: serverseitig (oder Worker) via node-vibrant / alternative Palette‑Extraction

### Visualisierung
- Web Audio API für lokale Playback‑Visuals (wenn Audio im Browser läuft)
- Sonst: „Fake‑VU“ aus RMS/Level Metadaten oder Server‑Side Analysis
- Rendering: Canvas/WebGL; heavy work per OffscreenCanvas/Worker

---

## 9) UX-Flows (Kernszenarien)

### Flow A: „Play a song“ (10 Sekunden Wow)
1. App öffnet → Hero zeigt „Continue Listening“ + „Random Album“  
2. User tippt Search / ⌘K → tippt 3 Buchstaben  
3. Instant Results (Tracks/Albums/Artists) + Quick Actions  
4. Tap/Enter → startet, Mini Player poppt mit Cover + Progress  
5. Swipe/Click → Expanded Now Playing mit Queue + Lyrics

### Flow B: „Browse Library“ (50k+ Tracks)
1. Library → Artists → (Virtualized list)  
2. Artist Detail: Top Albums, Popular Tracks, Filterchips  
3. Album → Tracklist → Multi‑select + enqueue/playlist/tag  
4. Keine Layout Shifts, Cover lazy mit BlurHash

### Flow C: „Multiroom Sync“
1. Devices Drawer  
2. Select Group / Create Group  
3. Drag Player in Group (oder „Join“)  
4. Master‑Volume + per‑Device Trim  
5. Move Playback zwischen Gruppen

---

## 10) Prototype-Konzept (Wireframe-Logik)

### Layout (Desktop)
- **Left Sidebar**: Navigation + Playlists + Devices Badge
- **Main**: 
  - Home: Continue / Discovery / Recently Added
  - Library: Split View (List links, Detail rechts)
- **Right Drawer**: Queue (toggle)
- **Bottom Bar**: Mini Player (immer)

### Layout (Tablet / Wall)
- Home als „Kacheln“ (Playlists / Radios / Rooms)
- Now Playing als Default Screen (große Targets)

---

## 11) Umsetzung: „First Mile“ Roadmap (praktisch)

**MVP++ (4–6 Wochen)**
- Home (Continue, Recently Added, Random Album)
- Search überall + Command Palette
- Library Virtualization + BlurHash + lazy album art
- Now Playing 3‑Level UI
- Devices Drawer + basic sync groups

**V1 (8–12 Wochen)**
- Focus‑Filter System
- Smart Playlists Regel‑Builder
- Discovery (Track Radio basic)
- PWA Shell + Image Caching

**V2 (Spicy)**
- Sonic Analysis + Sweet Fades
- Sharing, Multi‑User
- Themes/Widgets Marketplace (optional)

---

## 12) Quellen (Key Links)
- Svelte 5: https://svelte.dev/blog/svelte-5-is-alive  
- React 19: https://react.dev/blog/2024/12/05/react-19  
- Vue Vapor Roadmap: https://github.com/vuejs/core/issues/13687  
- Solid 2.0 Roadmap: https://github.com/solidjs/solid/discussions/2425  
- View Transitions: https://web.dev/learn/css/view-transitions-spas  
- OffscreenCanvas: https://web.dev/articles/offscreen-canvas  
- BlurHash: https://github.com/woltapp/blurhash  
- node-vibrant: https://vibrant.dev/guides/get-started/  
- Plex Sonic Analysis: https://support.plex.tv/articles/sonic-analysis-music/  
- Navidrome Overview: https://www.navidrome.org/docs/overview/  
- Material Skin: https://github.com/CDrummond/lms-material

---

*Wenn du willst, kann ich als nächsten Schritt ein „Design Token Sheet“ (Farben/Typo/Radius/Spacing), eine Component‑Liste (Svelte) und 2–3 konkrete Wireframe‑Screens (als Markdown‑Skizzen) dazulegen.*
