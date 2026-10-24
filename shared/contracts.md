# Contracts

Source of truth: `backend/app/schemas.py` (pydantic). TS mirror: `shared/types.ts`.
Change one → change both in the same PR.

## REST

| Method | Path | Returns | Owner |
|---|---|---|---|
| GET | `/health` | `{"ok": true}` | A |
| GET | `/fleet` | `Vehicle[]` | A |
| GET | `/depots` | `Depot[]` | A |
| GET | `/missions` | `Mission[]` | A |
| GET | `/parts` | `Part[]` | A |
| GET | `/suppliers` | `Supplier[]` | A |
| GET | `/cities` | `{id, name, lat, lng}[]` | B |
| POST | `/scenario/{id}` (`1`,`2`,`3`) | `{"started": id}`; work streams on `/events` | A |
| POST | `/reset` | `{"ok": true}`: reloads seed data | A |
| GET | `/events` | SSE, each `data:` is one `AgentEvent` JSON | A |
| GET | `/incidents` / `/incidents/{id}` | `Incident[]` / `Incident` | A |
| GET | `/vehicles/{id}/health` | `{vehicle_id, type, zones: {engine\|cooling\|electrical\|brakes\|transmission\|tires\|fuel: {status: ok\|warn\|fail, reasons: str[], part_id, incident_id}}}`. Drives the 3D part colors | A |
| GET | `/fuel/{vehicle_id}` | `{vehicle_id, expected_l_100km, actual_l_100km, delta_pct, logs: [{ts, litres, odometer_km, l_100km, station_city, cost_mad}], anomalies: FuelAnomaly[]}`. Right-side fuel drawer | B |
| GET | `/missions/{id}/path` | `{mission_id, path: cityId[], coords: [lat,lng][], progress_pct}`. Road line + vehicle position on the map | B |
| GET | `/fuel/summary` | `{vehicle_id, expected_l_100km, actual_l_100km, delta_pct, anomalies: FuelAnomaly[]}[]` | B |
| POST | `/route/compare` body `{from, to, vehicle_id}` | `RouteOption[]` (shortest, cheapest, fastest) | B |
| GET | `/missions/{id}/eta` | `{mission_id, stops: [{city, eta, late_min}]}` | B |

## SSE flow per scenario (what the frontend should expect)

1. `system/alert`: scenario started, `vehicle_id` set.
2. `maintenance/tool_call` + `tool_result` (several): telemetry, parts, suppliers, depots.
3. `maintenance/decision`: `data.incident_id` → fetch `/incidents/{id}`.
4. `orchestrator/handoff` → `delay/...` and `fuel/...` events.
5. `orchestrator/decision`: final summary. Scenario done.

Frontend rule: on any event with `data.incident_id`, refetch that incident; on any event with `vehicle_id`, refetch `/fleet`.

## Agent plug-in signature

```python
async def run(event: dict, state: State) -> list[AgentEvent]: ...
```
Agents push events through `state.emit(AgentEvent)`, never write SSE directly.

## Units
Money in MAD (int), distance km, time minutes (`_min`) or hours (`_hours`), fuel litres. Times ISO local `YYYY-MM-DDTHH:MM`.
