"""FastAPI entrypoint. Owner: Dev A. Dev B adds routes via APIRouter in routes_fuel.py."""
from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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


@app.post("/scenario/{scenario_id}")
async def scenario(scenario_id: int):
    if scenario_id not in state.scenarios:
        raise HTTPException(404, "unknown scenario")
    asyncio.create_task(run_scenario(scenario_id, state))
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


class StripApiPrefix:
    """The frontend calls /api/...; on a single deploy the routes above live at /..."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope["path"]
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope, path=path[4:] or "/", raw_path=None)
        await self.app(scope, receive, send)


app.add_middleware(StripApiPrefix)

# Serve the built frontend (frontend/dist) from the same service when it exists.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
