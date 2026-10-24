"""In-memory fleet state, event bus (SSE fan-out) and audit log."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from .schemas import AgentEvent, Depot, FuelAnomaly, Incident, Mission, Part, Supplier, Vehicle

DATA = Path(__file__).resolve().parents[1] / "data"


def _load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class State:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[AgentEvent]] = []
        self.reset()

    def reset(self) -> None:
        self.vehicles: dict[str, Vehicle] = {v["id"]: Vehicle(**v) for v in _load("vehicles.json")}
        self.depots: dict[str, Depot] = {d["id"]: Depot(**d) for d in _load("depots.json")}
        self.missions: dict[str, Mission] = {m["id"]: Mission(**m) for m in _load("missions.json")}
        self.parts: dict[str, Part] = {p["id"]: Part(**p) for p in _load("parts.json")}
        self.suppliers: dict[str, Supplier] = {s["id"]: Supplier(**s) for s in _load("suppliers.json")}
        self.road_graph: dict = _load("road_graph.json")
        self.fuel_logs: list[dict] = _load("fuel_logs.json")
        self.scenarios: dict[int, dict] = {s["id"]: s for s in _load("scenarios.json")}
        self.incidents: dict[str, Incident] = {}
        self.fuel_anomalies: dict[str, list[FuelAnomaly]] = {}  # vehicle_id -> anomalies (Dev B writes)
        self.etas: dict[str, dict] = {}  # mission_id -> {"stops": [{city, eta, late_min}]} (Dev B writes)
        self.audit: list[AgentEvent] = []

    # ---- event bus ----
    def subscribe(self) -> asyncio.Queue[AgentEvent]:
        q: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[AgentEvent]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def emit(self, agent: str, kind: str, title: str, detail: str = "", vehicle_id: str | None = None, **data) -> AgentEvent:
        ev = AgentEvent(id=uuid.uuid4().hex[:10], ts=datetime.now().isoformat(timespec="seconds"), agent=agent,
                        kind=kind, title=title, detail=detail, vehicle_id=vehicle_id, data=data)
        self.audit.append(ev)
        for q in self._subscribers:
            q.put_nowait(ev)
        return ev


state = State()
