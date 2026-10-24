"""Delay agent.

Python computes the start delay and every ETA / lateness (routing tools). The LLM only picks a better stop
order when there are several stops, and writes the message for the client.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..llm import Tool, run_agent
from ..schemas import AgentEvent
from ..state import State
from ..tools.fuel_stats import NOW
from ..tools.geo import road_km
from ..tools.routing import compare_routes, nearest_city

TAKEOVER_SPEED_KMH = 70  # takeover truck driving to the broken one
TRANSFER_MIN = 30  # moving the pallets across

SYSTEM = """Tu es l'agent Retards d'une flotte marocaine. Un véhicule est tombé en panne et sa mission est reprise par
un autre véhicule. Les ETA sont calculés par des outils (n'invente jamais une heure ni un retard):
1. Lis la mission et le délai de départ (get_mission).
2. S'il y a plusieurs arrêts, teste d'autres ordres avec simulate_order et garde celui qui minimise le retard total
   en respectant au mieux les fenêtres horaires. S'il n'y a qu'un arrêt, ne change rien.
3. Rédige un message court et professionnel en français pour le client, avec la nouvelle heure d'arrivée et un
   mot d'excuse si l'arrêt est en retard (late_min > 0). Si tout est à l'heure, rassure le client.
Réponds à la fin UNIQUEMENT avec ce JSON:
{"stop_order": [city_id], "client_message_fr": str, "summary_fr": str}
summary_fr = 1-2 lignes pour le responsable de flotte (nouvelle ETA, retard, ordre choisi)."""


def start_delay(state: State, event: dict) -> tuple[float, str, str]:
    """(delay in minutes before the mission vehicle starts rolling, how, start city = where the load is)."""
    inc = state.incidents[event["incident_id"]]
    broken = state.vehicles[event["vehicle_id"]]
    start_city = nearest_city(state, broken.position.lat, broken.position.lng)
    di = inc.driver_instruction
    if di and di.replacement_vehicle_id:
        return float(di.eta_min), f"remplacement {di.replacement_vehicle_id} depuis {di.depot_city}", start_city
    if inc.takeover_vehicle_id:
        t = state.vehicles[inc.takeover_vehicle_id]
        reach = road_km(t.position, broken.position) / TAKEOVER_SPEED_KMH * 60
        return round(reach + TRANSFER_MIN), f"{t.id} rejoint {broken.id} puis transfert des palettes", start_city
    return 0.0, "aucun véhicule de remplacement", start_city


def compute_etas(state: State, mission_id: str, order: list[str], delay_min: float, start_city: str) -> list[dict]:
    """ETA + lateness per stop, visiting the stops in `order` (city ids) with the mission's current vehicle."""
    m = state.missions[mission_id]
    stops = {s.city: s for s in m.stops}
    t, here, out = NOW + timedelta(minutes=delay_min), start_city, []
    for city in order:
        if city != here:
            t += timedelta(hours=next(r for r in compare_routes(state, here, city, m.vehicle_id) if r.label == "fastest").hours)
        late = max(0, round((t - datetime.fromisoformat(stops[city].window_end)).total_seconds() / 60))
        out.append({"city": city, "eta": t.isoformat(timespec="minutes"), "late_min": late})
        here = city
    return out


def _valid_order(state: State, mission_id: str, order) -> list[str]:
    original = [s.city for s in state.missions[mission_id].stops]
    ok = isinstance(order, list) and len(order) == len(original) and sorted(order) == sorted(original)
    return order if ok and len(set(original)) == len(original) else original


async def run(event: dict, state: State) -> list[AgentEvent]:
    """event: {"mission_id", "incident_id", "vehicle_id", "tag"}. Stores state.etas[mission_id]."""
    mid, vid = event["mission_id"], event["vehicle_id"]
    m = state.missions[mid]
    delay_min, how, start_city = start_delay(state, event)
    original = [s.city for s in m.stops]
    events: list[AgentEvent] = []

    def emit(*args, **kw) -> AgentEvent:
        events.append(ev := state.emit(*args, **kw))
        return ev

    def get_mission(mission_id: str) -> dict:
        return {"mission": state.missions[mission_id].model_dump(), "mission_vehicle_id": state.missions[mission_id].vehicle_id,
                "start_delay_min": delay_min, "start_delay_reason": how, "start_city": start_city,
                "current_order": original, "current_etas": compute_etas(state, mission_id, original, delay_min, start_city)}

    def simulate_order(order: list[str]) -> dict:
        etas = compute_etas(state, mid, _valid_order(state, mid, order), delay_min, start_city)
        return {"stops": etas, "total_late_min": sum(s["late_min"] for s in etas)}

    tools = [
        Tool("get_mission", "Mission (arrêts, fenêtres horaires), délai de départ et ETA actuelles.",
             {"type": "object", "properties": {"mission_id": {"type": "string"}}, "required": ["mission_id"]}, get_mission),
        Tool("simulate_order", "ETA et retard par arrêt pour un ordre de visite donné (liste d'ids de villes).",
             {"type": "object", "properties": {"order": {"type": "array", "items": {"type": "string"}}}, "required": ["order"]},
             simulate_order),
    ]
    user = (f"Mission {mid} (client {m.client}), véhicule en panne {vid}, nouveau véhicule {m.vehicle_id}. "
            f"Départ retardé de {delay_min:.0f} min ({how}). Arrêts: {original}.")
    out = await run_agent(tag=event["tag"], agent="delay", system=SYSTEM, user=user, tools=tools, emit=emit, vehicle_id=vid)

    order = _valid_order(state, mid, out.get("stop_order"))
    stops = compute_etas(state, mid, order, delay_min, start_city)
    state.etas[mid] = {"mission_id": mid, "stops": stops, "client_message_fr": out.get("client_message_fr", ""),
                       "start_delay_min": delay_min, "vehicle_id": m.vehicle_id}
    late = [s for s in stops if s["late_min"] > 0]
    emit("delay", "decision", f"Mission {mid}: " + (f"retard max {max(s['late_min'] for s in late)} min" if late else "dans les temps"),
         out.get("summary_fr", ""), vehicle_id=vid, mission_id=mid, incident_id=event["incident_id"], stops=stops,
         client_message_fr=state.etas[mid]["client_message_fr"])
    return events
