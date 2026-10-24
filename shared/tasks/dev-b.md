# Dev B: Fuel agent + Delay agent + routing

Branch: `feat/fuel-delay`. Read first: `shared/contracts.md`, `backend/app/schemas.py`, `backend/app/llm.py`, `backend/app/agents/maintenance.py` (copy its pattern).
Run tests: `cd backend && python -m pytest -q`. Never edit Dev A files (`main.py`, `state.py`, `llm.py`, `maintenance.py`, `orchestrator.py`). If you need a change there, ask Dev A.

## Rules (same as the maintenance agent)
- **Numbers come from Python tools, never from the LLM.** The LLM classifies causes, decides, and writes text.
- LLM calls go through `run_agent(tag=event["tag"], agent="fuel"|"delay", system=..., user=..., tools=[Tool(...)], emit=state.emit, vehicle_id=...)`. It returns the final JSON dict and auto-records `replay_cache/<tag>.json`.
- Timeline events: `state.emit(agent, kind, title, detail, vehicle_id=..., **data)`.
- Data you read: `state.road_graph` (`meta`, `cities`, `edges`), `state.fuel_logs`, `state.vehicles`, `state.missions`, `state.incidents`.
- Data you write: `state.fuel_anomalies[vehicle_id] = [FuelAnomaly]`, `state.etas[mission_id] = {...}` (slots already exist).

## 1. `app/tools/routing.py` (start here, ~45 min)
- Build an `nx.MultiGraph` from `road_graph.edges`. Parallel edges are on purpose: highway with toll vs national road with no toll.
- Per edge, for a given vehicle:
  - `fuel_l = km * vehicle.base_l_100km / 100`
  - `fuel_cost = fuel_l * meta.diesel_mad_per_l`
  - `toll = toll_mad * (meta.truck_toll_multiplier if truck else 1)`
  - `hours = km / meta.speed_kmh[road][vehicle.type]`
  - `driver_cost = hours * meta.driver_cost_mad_per_hour`
  - `total = fuel_cost + toll + driver_cost`
- `compare_routes(state, from_city, to_city, vehicle_id) -> list[RouteOption]`: 3 options, `shortest` (min km), `cheapest` (min total), `fastest` (min hours). On a MultiGraph, pass a weight function that returns the min over parallel edges, and remember which edge won for the totals.
- `mission_path(state, mission_id) -> {mission_id, path, coords, progress_pct}`: cheapest path origin → each stop in order. `coords` = `[lat, lng]` per city. `progress_pct` = how far the mission's current vehicle is along it (nearest city index / total is fine).
- Expected: Casablanca → Fès cheapest should differ from shortest (national roads skip tolls). Check it in a test.

## 2. `app/tools/fuel_stats.py` (~40 min)
- `fuel_stats(state, vehicle_id) -> {vehicle_id, expected_l_100km, actual_l_100km, delta_pct, logs, anomalies}`
  - logs sorted by ts; per fill `l_100km = litres / (odo - prev_odo) * 100`; add `cost_mad = litres * price_mad_l`
  - actual = last 7 days (litres sum / km sum); expected = `vehicle.base_l_100km`
- Detectors → `FuelAnomaly` (leave `probable_cause` and `note` empty, the LLM fills them):
  - `overconsumption`: 7-day delta > +15%
  - `fill_over_capacity`: litres > `vehicle.tank_l`
  - `fill_without_km`: km since previous fill < 20 with litres > 50 (treat km <= 0 the same)
  - `excessive_idle`: `telemetry.idle_pct_7d > 25`
- Seeded truth, so your tests must find exactly this:
  - **T-12** overconsumption ≈ +22% (dragging brake caliper)
  - **T-05** fill 455 L > 400 L tank, then 180 L with 0 km (fuel card fraud)
  - **T-09** excessive idle 31%
  - every other vehicle clean

## 3. `app/agents/fuel.py` (~40 min)
```python
async def run(event: dict, state: State) -> list[AgentEvent]: ...
# event = {"vehicle_id", "tag", optional "incident_id"}
```
- Compute `fuel_stats` and emit an `alert` per anomaly.
- LLM tools: `get_fuel_stats`, `get_vehicle` (telemetry: brake wear, DTC, idle), `compare_routes`. The LLM returns `{"anomalies": [{"kind", "probable_cause": mechanical|behavior|fraud|detour|unknown, "note"}], "route_advice": str, "manager_note_fr": str}`.
- Merge the causes and notes into the `FuelAnomaly` objects and store them in `state.fuel_anomalies`.
- If any cause is `mechanical`, emit `state.emit("fuel", "handoff", "→ Maintenance", note, vehicle_id=vid)`. The orchestrator already sends T-12 to maintenance next.
- When called after an incident (`incident_id` set), give the extra fuel and toll cost of the detour to the depot (`compare_routes` from the nearest city to the depot city).

## 4. `app/agents/delay.py` (~40 min)
```python
async def run(event: dict, state: State) -> list[AgentEvent]: ...
# event = {"mission_id", "incident_id", "vehicle_id", "tag"}
```
- The mission's `vehicle_id` was already switched by the orchestrator, to the replacement (scenario 1) or the takeover truck T-03 (scenario 2).
- Start delay:
  - replacement: `incident.driver_instruction.eta_min`
  - takeover: the time for T-03 to reach the broken truck (distance / 70 km/h) + 30 min to transfer pallets
- ETA per stop = now (2026-10-24T08:00 sim clock is fine) + start delay + `routing` hours. `late_min = max(0, eta - window_end)`.
- LLM: if several stops, propose a better order. Draft `client_message_fr` per impacted client.
- Store `state.etas[mission_id] = {"mission_id", "stops": [{city, eta, late_min}], "client_message_fr"}` and emit a `decision`.

## 5. `app/routes_fuel.py`: `router = APIRouter()`
- `GET /cities`
- `GET /fuel/summary`
- `GET /fuel/{vehicle_id}`
- `POST /route/compare` body `{from, to, vehicle_id}`
- `GET /missions/{id}/path`
- `GET /missions/{id}/eta`

Exact response shapes are in `shared/contracts.md`. Tell Dev A to uncomment the two `include_router` lines in `main.py`. The orchestrator picks up `agents/fuel.py` and `agents/delay.py` on its own once they exist.

## 6. `tests/test_fuel_delay.py`
Routing (cheapest ≠ shortest on Casa→Fès), the 3 seeded anomalies, and an ETA after the scenario 2 takeover. For an LLM end-to-end test, copy the replay pattern in `tests/test_agent_a.py`.

## Done =
`curl localhost:8000/fuel/T-12` shows +22% with an LLM note. Scenario 3 on the timeline goes fuel → handoff → maintenance → orchestrator. Scenario 2 shows the delay agent's new ETA for Pharma Sud via T-03.
