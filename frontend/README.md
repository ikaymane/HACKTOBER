# FleetSense frontend

React + Vite + TS + Tailwind v4. Map: MapLibre (CARTO dark) + deck.gl. Inspector: react-three-fiber on `public/models/*.glb`.

```bash
# backend, no API key
cd ../backend && MOCK=1 uvicorn app.main:app --reload --port 8000
# frontend
npm install && npm run dev   # http://localhost:5173
```

- REST goes through the Vite proxy `/api` → `:8000`. SSE connects straight to `:8000/events` in dev (the proxy holds back SSE headers); override with `VITE_EVENTS_URL`.
- Dev B endpoints (`/missions/{id}/path`, `/fuel/{id}`, `/route/compare`) fall back to local computations in `src/api.ts` on 404, so the UI works before they ship. Road geometry comes from the public OSRM demo server, cached in localStorage, straight lines if offline.
- Shortcuts: `1` `2` `3` scenarios, `R` reset; inspector `←` `→` vehicle, `E` exploded view, `F` fuel drawer, `Esc`.
