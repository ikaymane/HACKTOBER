"""Dev B REST routes: cities, fuel, route comparison, mission path + ETA. Mounted by main.py."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .agents.delay import compute_etas
from .state import state
from .tools.fuel_stats import fleet_fuel_kpi, fuel_stats
from .tools.routing import compare_routes, mission_path

router = APIRouter()


class RouteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_city: str = Field(alias="from")
    to: str
    vehicle_id: str


def _vehicle(vehicle_id: str) -> None:
    if vehicle_id not in state.vehicles:
        raise HTTPException(404, "unknown vehicle")


def _mission(mission_id: str) -> None:
    if mission_id not in state.missions:
        raise HTTPException(404, "unknown mission")


@router.get("/cities")
def cities():
    return [{k: c[k] for k in ("id", "name", "lat", "lng")} for c in state.road_graph["cities"]]


@router.get("/fuel/summary")  # declared before /fuel/{vehicle_id}
def fuel_summary():
    out = []
    for vid in state.vehicles:
        s = fuel_stats(state, vid)
        out.append({k: s[k] for k in ("vehicle_id", "expected_l_100km", "actual_l_100km", "delta_pct", "anomalies")})
    return out


@router.get("/fuel/kpi")  # declared before /fuel/{vehicle_id}
def fuel_kpi():
    return fleet_fuel_kpi(state)


@router.get("/fuel/{vehicle_id}")
def fuel(vehicle_id: str):
    _vehicle(vehicle_id)
    return fuel_stats(state, vehicle_id)


@router.post("/route/compare")
def route_compare(req: RouteRequest):
    _vehicle(req.vehicle_id)
    try:
        return compare_routes(state, req.from_city, req.to, req.vehicle_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/missions/{mission_id}/path")
def mission_path_route(mission_id: str):
    _mission(mission_id)
    return mission_path(state, mission_id)


@router.get("/missions/{mission_id}/eta")
def mission_eta(mission_id: str):
    _mission(mission_id)
    if mission_id in state.etas:  # set by the delay agent after an incident
        return state.etas[mission_id]
    m = state.missions[mission_id]  # no incident: plain schedule from the origin
    return {"mission_id": mission_id,
            "stops": compute_etas(state, mission_id, [s.city for s in m.stops], 0, m.origin)}
