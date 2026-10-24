"""Depots + replacement vehicles + load takeover by another truck on the road."""
from __future__ import annotations

import re

from ..state import State
from .geo import road_km

AVG_SPEED_KMH = {"truck": 70, "ambulance": 90}  # broken vehicle limping / replacement driving


def find_replacement(state: State, vehicle_id: str) -> list[dict]:
    """Depots sorted by distance from the broken vehicle, with matching spare vehicles."""
    v = state.vehicles[vehicle_id]
    out = []
    for d in state.depots.values():
        km = road_km(v.position, d.position)
        spares = [sid for sid in d.spare_vehicles
                  if state.vehicles[sid].type == v.type and state.vehicles[sid].status == "available"]
        out.append({
            "depot_id": d.id, "city": d.city, "distance_km": km,
            "eta_min": round(km / AVG_SPEED_KMH[v.type] * 60), "has_workshop": d.has_workshop,
            "spare_vehicles_same_type": spares,
        })
    return sorted(out, key=lambda x: x["distance_km"])


def _pallets(text: str) -> int:
    m = re.search(r"(\d+)\s*palettes?", text)
    return int(m.group(1)) if m else 0


def find_load_takeover(state: State, vehicle_id: str) -> list[dict]:
    """Other trucks on mission that pass by the same destination and have room for the load."""
    v = state.vehicles[vehicle_id]
    m = state.missions.get(v.mission_id or "")
    if not m or v.type != "truck":
        return []
    need = sum(_pallets(s.cargo) for s in m.stops)
    dests = {s.city for s in m.stops}
    out = []
    for other in state.missions.values():
        ov = state.vehicles[other.vehicle_id]
        if other.id == m.id or ov.type != "truck" or ov.status != "on_mission":
            continue
        if dests & {s.city for s in other.stops} and other.capacity_free_pallets >= need:
            out.append({"vehicle_id": ov.id, "mission_id": other.id, "free_pallets": other.capacity_free_pallets,
                        "pallets_needed": need, "distance_km": road_km(v.position, ov.position),
                        "shared_destinations": sorted(dests & {s.city for s in other.stops})})
    return sorted(out, key=lambda x: x["distance_km"])
