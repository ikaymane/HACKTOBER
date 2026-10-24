# Frontend spec (Dev C)

Goal: a professional fleet-operations dashboard. Dark ops-room look, a 3D map with trucks and ambulances on their real roads, and a 3D exploded view of a vehicle showing exactly which part failed and what the agent decided.

## Stack
React + Vite + TypeScript + Tailwind.
- Map: `react-map-gl/maplibre` + `maplibre-gl` with the free CARTO dark style `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json` (no key). Pitch 50° for the 3D feel.
- Vehicles on map: deck.gl `ScenegraphLayer` (`@deck.gl/react @deck.gl/layers @deck.gl/mesh-layers @loaders.gl/gltf`) with low-poly GLB models: Kenney "Car Kit" (CC0) has a delivery truck and an ambulance. Mission roads: deck.gl `PathLayer` from `/missions/{id}/path`. Fallback if time is short: colored `IconLayer` markers.
- Vehicle 3D viewer: `@react-three/fiber` + `@react-three/drei`, loading **`assets/models/truck.glb` / `ambulance.glb`** (made in Blender, one node per part with `userData.zone/part_id/label_fr/explode_dir`; see `assets/models/README.md`). The zone groups below describe what is inside them.
- Charts: `recharts`. Animation: `framer-motion` for panels.

Design tokens: bg `#0B0F14`, panel `#121821`, border `#1F2A37`, text `#E5E7EB`, muted `#94A3B8`, accent `#22D3EE`, ok `#10B981`, warn `#F59E0B`, fail `#EF4444`. Fonts: Inter (UI), JetBrains Mono (numbers, ids).

## Screen 1: Ops dashboard
```
┌ KPI bar: vehicles on mission · open incidents · penalties at risk / avoided (MAD) · fuel spend today ┐
├ Fleet list (left, 280px) ┬ 3D map (center) ─────────────────────────┬ Agent timeline (right, 360px) ┤
│ id, type icon, status    │ trucks/ambulances on their roads,        │ live SSE /events, colored by   │
│ chip, mission, alert dot │ broken vehicle pulses red, depots as     │ agent, tool calls collapsible, │
│                          │ pins; click vehicle → Screen 2           │ decisions highlighted          │
├ Scenario bar: [1 Ambulance alternateur] [2 Camion surchauffe] [3 Carburant T-12] [Reset] ───────────┤
```
On SSE event with `vehicle_id` → refetch `/fleet` (map + list update). On `data.incident_id` → refetch the incident and show a toast "Incident INC-002 · T-07 · Pompe à eau".

## Screen 2: Vehicle inspector (full-screen modal over the map)
- Header: `T-07 · Renault T 460 · 78901-A-6 · driver · mission M-107 → Marrakech`, health chip. **◀ ▶ buttons (and ←/→ keys) switch to the previous/next vehicle** in the fleet list.
- Center: 3D vehicle, orbit controls. Button "Vue éclatée" (auto-on if an incident exists): every zone group slides out along its own direction (lerp 0→1, ~600 ms), the body shell turns semi-transparent.
- Zone groups (one `<group>` each, colored from `/vehicles/{id}/health`):
  - engine: block + turbo cylinder
  - cooling: radiator panel at front + water pump disc
  - electrical: alternator cylinder + battery box
  - brakes: discs + calipers inside each wheel
  - transmission: gearbox + driveshaft
  - tires: wheels (6 on truck, 4 on ambulance)
  - fuel: tank on chassis side
  Truck = cab + long cargo box; ambulance = van body + light bar. Status colors: ok slate, warn amber, fail red with emissive pulse + small floating label.
- **Click a part → left popup (clean card)**, fetched from the incident of that zone:
  - part name, zone, severity badge, confidence bar
  - "Preuves de l'agent": `diagnosis.evidence` list
  - "Proposition": REPAIR or REPLACE badge, reason, cost MAD, downtime h
  - supplier table from `suppliers` (KPI bars: price, delivery, on-time, warranty, rating; chosen row highlighted + `supplier_reason`)
  - driver instruction (depot, km, ETA, replacement vehicle) + penalty block (at risk / avoided, amount, mitigation)
  - "Rapport envoyé à la société": `report_fr`
  Healthy part click → small card with `reasons` and "Aucun problème détecté".
- **Right drawer "Carburant"** (toggle button, open by default if a fuel anomaly exists), from `/fuel/{vehicle_id}`: L/100 km line vs expected, delta % badge, fill-up table, anomaly cards with the agent's note, and the route comparison (shortest / cheapest / fastest) from `/route/compare`.

## Build order (cut from the bottom if late)
1. Layout + KPI bar + fleet list + timeline on SSE (use `MOCK=1` backend, no key needed)
2. Map with markers + paths
3. Vehicle inspector: procedural 3D + health colors + exploded view + part popup
4. Fuel drawer
5. ◀ ▶ switching + keyboard
6. GLB models on the map instead of markers

Run the backend without an API key: `MOCK=1 uvicorn app.main:app --reload` (fake agent stream), or `REPLAY=1` once Dev A has committed recorded runs.
