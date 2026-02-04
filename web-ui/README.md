# Resonance Web UI

Modern web interface for Resonance music server, built with Svelte 5, SvelteKit, and Tailwind CSS v4.

## 🚀 Features

- **Now Playing** - Album art, progress bar, playback controls
- **Player Selection** - Switch between multiple players
- **Volume Control** - Slider with mute toggle
- **Library Browser** - Browse Artists → Albums → Tracks
- **Queue Management** - View and manage the current playlist
- **Search** - Quick search across your music library
- **Real-time Updates** - Via Cometd/long-polling

## 🛠️ Tech Stack

- **Svelte 5** with Runes for reactive state
- **SvelteKit** for routing and build
- **Tailwind CSS v4** with CSS-native engine
- **Vite 6** for blazing fast builds
- **TypeScript** for type safety
- **Lucide** for beautiful icons

## 📦 Installation

```bash
# Navigate to web-ui directory
cd resonance/web-ui

# Install dependencies
npm install

# Start development server
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies API requests to the Python backend at `http://localhost:9000`.

## 🔧 Development

### Prerequisites

Make sure the Resonance Python backend is running:

```bash
cd resonance
micromamba run -p ".build/mamba/envs/resonance-env" python -m resonance --verbose
```

### Commands

```bash
# Development with hot reload
npm run dev

# Type checking
npm run check

# Build for production
npm run build

# Preview production build
npm run preview
```

### Project Structure

```
web-ui/
├── src/
│   ├── app.css              # Global styles + Tailwind
│   ├── app.html             # HTML template
│   ├── lib/
│   │   ├── api.ts           # API client (JSON-RPC + REST)
│   │   ├── components/      # Svelte components
│   │   │   ├── NowPlaying.svelte
│   │   │   ├── PlayerSelector.svelte
│   │   │   ├── Queue.svelte
│   │   │   ├── SearchBar.svelte
│   │   │   └── TrackList.svelte
│   │   └── stores/
│   │       └── player.svelte.ts  # Player state (Svelte 5 runes)
│   └── routes/
│       ├── +layout.svelte   # Root layout
│       ├── +layout.ts       # Layout options
│       ├── +page.svelte     # Main page
│       └── +page.ts         # Page options
├── static/                  # Static assets (favicon, etc.)
├── package.json
├── svelte.config.js
├── tsconfig.json
└── vite.config.ts
```

## 🎨 Design

The UI uses a **Catppuccin Mocha** inspired dark theme with:

- **Background**: Deep navy/purple tones
- **Accent**: Soft lavender/purple
- **Glass effect**: Frosted glass cards with blur
- **Smooth animations**: Transitions and micro-interactions

## 🔌 API Integration

The frontend communicates with Resonance via:

1. **JSON-RPC** (`/jsonrpc.js`) - LMS-compatible API
2. **REST API** (`/api/*`) - Modern endpoints
3. **Cometd** (`/cometd`) - Real-time updates (planned)

See `src/lib/api.ts` for the TypeScript API client.

## 📱 Responsive Design

- **Desktop**: Full layout with sidebar queue
- **Tablet**: Collapsible queue
- **Mobile**: Stack layout (planned)

## 🚧 TODO

- [ ] Cometd real-time integration
- [ ] Cover art display
- [ ] Drag & drop queue reordering
- [ ] Mobile-optimized layout
- [ ] Settings page
- [ ] Keyboard shortcuts
- [ ] Volume visualization
- [ ] Playlist save/load

## 📄 License

GPL v2 - Same as Resonance