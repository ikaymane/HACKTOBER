"""Road routing on the Moroccan road graph: shortest / cheapest / fastest per vehicle.

The graph is a MultiGraph on purpose: a city pair can have a highway (toll, fast) and a national road
(free, slower). Every number here is deterministic, the LLM only reads it.
"""
from __future__ import annotations

import networkx as nx

from ..schemas import RouteOption, Vehicle
from ..state import State
from .geo import haversine_km

LABELS = {"shortest": "km", "cheapest": "total", "fastest": "hours"}


def _edge_attrs(meta: dict, e: dict, v: Vehicle) -> dict:
    fuel_l = e["km"] * v.base_l_100km / 100
    fuel_cost = fuel_l * meta["diesel_mad_per_l"]
    toll = e["toll_mad"] * (meta["truck_toll_multiplier"] if v.type == "truck" else 1)
    hours = e["km"] / meta["speed_kmh"][e["road"]][v.type]
    driver_cost = hours * meta["driver_cost_mad_per_hour"]
    return {"km": e["km"], "fuel_l": fuel_l, "fuel_cost": fuel_cost, "toll": toll, "hours": hours,
            "driver_cost": driver_cost, "total": fuel_cost + toll + driver_cost, "road": e["road"]}


def build_graph(state: State, vehicle: Vehicle) -> nx.MultiGraph:
    g = nx.MultiGraph()
    rg = state.road_graph
    g.add_nodes_from(c["id"] for c in rg["cities"])
    for e in rg["edges"]:
        g.add_edge(e["from"], e["to"], **_edge_attrs(rg["meta"], e, vehicle))
    return g


def _best_option(g: nx.MultiGraph, a: str, b: str, label: str) -> RouteOption:
    key = LABELS[label]

    def weight(_u, _v, parallel: dict) -> float:  # min over parallel edges
        return min(d[key] for d in parallel.values())

    path = nx.shortest_path(g, a, b, weight=weight)
    legs = [min(g.get_edge_data(u, v).values(), key=lambda d: d[key]) for u, v in zip(path, path[1:])]
    s = lambda k: sum(d[k] for d in legs)  # noqa: E731
    return RouteOption(label=label, path=path, km=round(s("km"), 1), hours=round(s("hours"), 2),
                       fuel_l=round(s("fuel_l"), 1), fuel_cost_mad=round(s("fuel_cost")),
                       toll_mad=round(s("toll")), driver_cost_mad=round(s("driver_cost")),
                       total_cost_mad=round(s("total")))


def compare_routes(state: State, from_city: str, to_city: str, vehicle_id: str) -> list[RouteOption]:
    cities = {c["id"] for c in state.road_graph["cities"]}
    for c in (from_city, to_city):
        if c not in cities:
            raise ValueError(f"unknown city {c!r}")
    g = build_graph(state, state.vehicles[vehicle_id])
    return [_best_option(g, from_city, to_city, label) for label in LABELS]


def nearest_city(state: State, lat: float, lng: float) -> str:
    return min(state.road_graph["cities"], key=lambda c: haversine_km(lat, lng, c["lat"], c["lng"]))["id"]


def mission_path(state: State, mission_id: str) -> dict:
    """Cheapest path origin -> each stop in order, plus how far the current vehicle is along it."""
    m = state.missions[mission_id]
    v = state.vehicles[m.vehicle_id]
    g = build_graph(state, v)
    path: list[str] = [m.origin]
    for stop in m.stops:
        if stop.city != path[-1]:
            path += _best_option(g, path[-1], stop.city, "cheapest").path[1:]
    by_id = {c["id"]: c for c in state.road_graph["cities"]}
    here = nearest_city(state, v.position.lat, v.position.lng)
    # the vehicle may sit on a city that appears twice (loop): take the first one
    idx = path.index(here) if here in path else min(
        range(len(path)), key=lambda i: haversine_km(v.position.lat, v.position.lng, by_id[path[i]]["lat"], by_id[path[i]]["lng"]))
    progress = round(100 * idx / (len(path) - 1)) if len(path) > 1 else 0
    return {"mission_id": mission_id, "path": path,
            "coords": [[by_id[c]["lat"], by_id[c]["lng"]] for c in path], "progress_pct": progress}
