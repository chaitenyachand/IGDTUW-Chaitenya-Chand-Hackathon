# SENTINEL terminal (frontend)

React 19 + TanStack Start/Router/Query + Tailwind 4 single-page terminal for the SENTINEL risk-intelligence platform.

```bash
cp .env.example .env.local     # set VITE_API_BASE_URL and VITE_WS_URL (defaults below)
npm install
npm run dev                    # http://localhost:8080
npm run build                  # production build
```

`.env.local` for a local backend:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/signals
```

The terminal (`/app`) renders real API data only. Ten views: Overview, Signals, PRECEDENT, Stress Lab, Adaptive Index, Exposure, Portfolio, Model, Audit, Alerts. See the root README for the full system.
