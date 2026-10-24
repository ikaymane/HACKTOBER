# Dev C: Frontend (dashboard + 3D)

Branch: `feat/frontend`. You own `frontend/**`. The full UI spec (layout, 3D inspector, popups, fuel drawer, design tokens, build order) is in **`shared/frontend-spec.md`**: read it first. Types are in `shared/types.ts`.

## Setup (~15 min)
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm i tailwindcss @tailwindcss/vite three @react-three/fiber @react-three/drei maplibre-gl react-map-gl @deck.gl/react @deck.gl/layers @deck.gl/mesh-layers @loaders.gl/gltf recharts framer-motion lucide-react
npm i -D @types/three
```
- Pin the versions npm installs into `package.json`. Don't leave `latest`.
- `vite.config.ts`: Tailwind plugin, alias `@shared` → `../shared`, and proxy `/api` → `http://localhost:8000` with a path rewrite that strips `/api`. That avoids CORS and gives you one base URL.
- Backend without an API key: `cd backend && MOCK=1 uvicorn app.main:app --reload` (PowerShell: `$env:MOCK="1"; uvicorn app.main:app --reload`). It fakes the agent stream for the 3 scenarios.

## Suggested structure
```
src/
  api.ts                fetch helpers + useEvents() (EventSource on /api/events, event name "agent")
  store.ts              fleet, incidents, health, selectedVehicleId, events (zustand or useReducer)
  App.tsx               layout grid
  components/
    KpiBar.tsx FleetList.tsx AgentTimeline.tsx ScenarioBar.tsx Toasts.tsx
    map/FleetMap.tsx    MapLibre + deck.gl (PathLayer roads, Scenegraph/Icon vehicles, depots)
    inspector/
      Inspector.tsx     modal, header, ◀ ▶ switch (+ ←/→ keys)
      Vehicle3D.tsx     procedural truck/ambulance, one <group> per zone, explode lerp
      PartPopup.tsx     left card: evidence, repair/replace, suppliers, depot, penalty, report
      FuelDrawer.tsx    right drawer: chart, fill-ups, anomalies, route compare
```

## SSE snippet
```ts
const es = new EventSource("/api/events");
es.addEventListener("agent", (e) => {
  const ev: AgentEvent = JSON.parse((e as MessageEvent).data);
  pushEvent(ev);
  if (ev.vehicle_id) refetchFleet();
  if (ev.data.incident_id) refetchIncident(ev.data.incident_id as string);
});
```

## Endpoints: what exists now vs later
- **Now** (Dev A, on `main`):
  - `/fleet`, `/depots`, `/missions`, `/parts`, `/suppliers`, `/scenarios`
  - `POST /scenario/{id}`, `POST /reset`
  - `/events`, `/incidents`, `/incidents/{id}`, `/audit`
  - `/vehicles/{id}/health`
- **Later** (Dev B): `/fuel/{id}`, `/fuel/summary`, `/route/compare`, `/missions/{id}/path`, `/missions/{id}/eta`, `/cities`. Until then, mock them in `api.ts` with the shapes from `shared/contracts.md`. For the path, a straight line from the vehicle to the stop city is enough; city coords are in `backend/data/road_graph.json`.

## 3D notes
- **Inspector vehicle: models are DONE.** Use `assets/models/truck.glb` and `ambulance.glb` (copy to `public/models/`). Every part is a node with `userData.zone`, `part_id`, `label_fr` and `explode_dir`. Read `assets/models/README.md` and look at the `preview_*.png` renders.
- **Explode:** give each zone a direction vector and set `group.position = base + dir * explode * 1.5`, with `explode` animated 0→1 in `useFrame`. When exploded, set the body shell to `transparent opacity 0.15`.
- **Colors:** from `/vehicles/{id}/health` `zones[zone].status`. On `fail`, pulse `emissiveIntensity` and add a drei `<Html>` label.
- **Click:** `onClick` on the zone group opens `PartPopup` with `incident_id` from health → `/incidents/{id}`.
- **Map models:** Kenney "Car Kit" (CC0, kenney.nl) includes a delivery truck and an ambulance as GLB. Put them in `public/models/`. Use markers first and swap in the models last.

## Your second job (last 40 min)
- **README top:** problem, solution, a screenshot, an architecture diagram (Mermaid is fine), how the LLM is used, how to run.
- **2–3 min screen recording** of scenarios 1→2→3: map → click vehicle → exploded view → part popup → fuel drawer.

## Done =
A judge opens the app, clicks "Scénario 2" and sees:
- T-07 turn red on the map
- the agents working on the timeline
- clicking T-07 explodes the truck with a red cooling zone
- clicking the pump shows the evidence, REPLACE, the supplier ranking and "pénalité évitée grâce à T-03"
