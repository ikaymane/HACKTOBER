"""FastAPI entrypoint. Owner: Dev A. Dev B adds routes via APIRouter in routes_fuel.py."""
from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from .simulator import run_scenario
from .state import state
from .tools.health import vehicle_health

load_dotenv()
app = FastAPI(title="FleetSense")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from .routes_fuel import router as fuel_router  # noqa: E402  (Dev B: fuel, routing, ETA)

app.include_router(fuel_router)

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_running: set[int] = set()


class ApiGateway:
    """Strips /api (the built frontend calls /api/*, like the Vite dev proxy) and gzips everything but the
    SSE stream, which gzip would hold back until its buffer fills."""

    def __init__(self, inner):
        self.inner = inner
        self.gzip = GZipMiddleware(inner, minimum_size=1024)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.inner(scope, receive, send)
            return
        if scope["path"].startswith("/api/"):
            scope = {**scope, "path": scope["path"][4:]}
        await (self.inner if scope["path"] == "/events" else self.gzip)(scope, receive, send)


app.add_middleware(ApiGateway)


class CachedStatic(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.startswith("assets"):  # content-hashed filenames
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith("models"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/fleet")
def fleet():
    return list(state.vehicles.values())


@app.get("/vehicles/{vehicle_id}/health")
def health_of(vehicle_id: str):
    if vehicle_id not in state.vehicles:
        raise HTTPException(404, "unknown vehicle")
    return vehicle_health(state, vehicle_id)


@app.get("/depots")
def depots():
    return list(state.depots.values())


@app.get("/missions")
def missions():
    return list(state.missions.values())


@app.get("/parts")
def parts():
    return list(state.parts.values())


@app.get("/suppliers")
def suppliers():
    return list(state.suppliers.values())


@app.get("/scenarios")
def scenarios():
    return [{"id": s["id"], "title": s["title"], "vehicle_id": s["vehicle_id"]} for s in state.scenarios.values()]


async def _run_guarded(scenario_id: int) -> None:
    try:
        await run_scenario(scenario_id, state)
    finally:
        _running.discard(scenario_id)


@app.post("/scenario/{scenario_id}")
async def scenario(scenario_id: int):
    if scenario_id not in state.scenarios:
        raise HTTPException(404, "unknown scenario")
    # A second press would stack a duplicate incident on a vehicle whose mission already moved on.
    if scenario_id in _running or state.vehicles[state.scenarios[scenario_id]["vehicle_id"]].status == "breakdown":
        raise HTTPException(409, "scenario already running or done: reset first")
    _running.add(scenario_id)
    asyncio.create_task(_run_guarded(scenario_id))
    return {"started": scenario_id}


@app.post("/reset")
def reset():
    state.reset()
    return {"ok": True}


@app.get("/incidents")
def incidents():
    return list(state.incidents.values())


@app.get("/incidents/{incident_id}")
def incident(incident_id: str):
    if incident_id not in state.incidents:
        raise HTTPException(404, "unknown incident")
    return state.incidents[incident_id]


@app.post("/incidents/{incident_id}/approve")
def approve_incident(incident_id: str):
    """The agents only propose: the plan counts once the fleet manager signs it off, on the record."""
    if incident_id not in state.incidents:
        raise HTTPException(404, "unknown incident")
    inc = state.incidents[incident_id]
    if not inc.approved:
        inc.approved = True
        state.emit("system", "message", f"Plan {inc.id} approuvé par le responsable de flotte", "",
                   vehicle_id=inc.vehicle_id, incident_id=inc.id)
    return inc


@app.get("/audit")
def audit():
    return state.audit


@app.get("/events")
async def events():
    q = state.subscribe()

    async def gen():
        try:
            while True:
                ev = await q.get()
                yield {"event": "agent", "data": ev.model_dump_json()}
        finally:
            state.unsubscribe(q)

    return EventSourceResponse(gen())


if DIST.is_dir():  # after every API route: serves the production build, see run.py
    app.mount("/", CachedStatic(directory=DIST, html=True), name="frontend")
