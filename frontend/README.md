# ATLAS · Fleet Intelligence

A French-language fleet operations dashboard built with React, Vite, TypeScript, Tailwind, MapLibre, deck.gl, React Three Fiber, Recharts, and Framer Motion.

## Run

```sh
npm install
npm run dev
```

Open the URL printed by Vite. Demo mode is the default: eight vehicles, three incidents, supplier decisions, route comparison, and fuel records. No API key is needed. Scenario controls change only demo state. Reset restores the initial three incidents. Export downloads a JSON snapshot.

## Live backend

Copy `.env.example` to `.env.local`, set `VITE_DATA_MODE=live`, and restart Vite. Locally, `/api` is proxied to port 8000. Start Dev A's backend using `MOCK=1 uvicorn app.main:app --reload` or `REPLAY=1`. For hosted use, set `VITE_API_BASE_URL` to the backend HTTPS origin, enable CORS, and allow long-lived SSE connections. No automatic fallback to demo occurs after a live API error.

Expected contracts are defined in `src/types.ts`:

| Request | Response |
| --- | --- |
| `GET /fleet` | `Vehicle[]` |
| `GET /vehicles/:id/health` | `HealthZone[]` |
| `GET /incidents/:id` | `Incident` |
| `GET /missions/:id/path` | `{path: [longitude, latitude][]}` |
| `GET /fuel/:id` | `FuelData` |
| `GET /route/compare?vehicle_id=:id` | `RouteOption[]` |
| `GET /events` | SSE `data:` messages with `AgentEvent` JSON |
| `POST /scenarios/1`, `/2`, `/3` | JSON acknowledgement |
| `POST /reset` | JSON acknowledgement |

The supplied spec does not define scenario POST endpoints or complete field shapes. Adjust `src/api.ts` to match Dev A's actual API. SSE events containing `vehicle_id` refresh the fleet; events containing `data.incident_id` fetch the incident, show a toast, and refresh the open inspector. EventSource reconnects automatically. The UI displays connection failure without inventing live activity.

## Map and 3D

CARTO Dark Matter is the free basemap; OpenStreetMap/CARTO attribution remains visible. Demo road geometry is generated using OSRM routing from public city coordinates; rerun `node scripts/fetch-roads.mjs` to refresh it. These are illustrative missions, not real fleet telemetry. Demo vehicle positions snap to these routes. The map uses deck.gl PathLayer, interactive markers, 50-degree pitch, route toggles, recentering, and 2D/3D controls.

The inspector uses procedural geometry with all seven zone groups, individual part selection, damped exploded animation, translucent shells, severity colors and a pulsing failed component. Optional GLBs are documented in `public/assets/models/README.md`. Scenegraph map rendering is available when both GLBs are supplied; markers are the default supported fallback.

The interface adapts to mobile, supports reduced motion, keyboard vehicle navigation, Escape to close, focus trapping, and focus restoration. Fonts require Google Fonts access; local system fallbacks are provided. Map tiles and OSRM require internet. If WebGL is unavailable the fleet list still opens diagnostics.

## Checks

```sh
npm run build
npm test
```

Demo pricing and outcomes are illustrative. The dashboard proposes decisions; it does not place orders, dispatch drivers, or send company reports. Report text in demo mode is explicitly marked simulated.
