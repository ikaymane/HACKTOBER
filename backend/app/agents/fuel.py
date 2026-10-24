"""Fuel agent.

Python detects the anomalies and computes every figure (fuel_stats, routing). The LLM only classifies the
probable cause of each anomaly and writes the advice / manager note.
"""
from __future__ import annotations

from ..llm import Tool, run_agent
from ..schemas import AgentEvent, FuelAnomaly
from ..state import State
from ..tools.fuel_stats import fuel_stats
from ..tools.routing import compare_routes, nearest_city

CAUSES = ("mechanical", "behavior", "fraud", "detour", "unknown")

SYSTEM = """Tu es l'agent Carburant d'une flotte marocaine (camions et ambulances).
Les anomalies ont déjà été détectées par des outils; ta mission est de les expliquer, sans inventer de chiffre:
1. Lis les statistiques (get_fuel_stats) et la télémétrie du véhicule (get_vehicle: usure freins, codes défaut, ralenti).
2. Pour CHAQUE anomalie, choisis la cause probable:
   - mechanical: panne ou usure (ex. surconsommation + usure des freins élevée ou code défaut frein/moteur)
   - behavior: conduite ou ralenti excessif
   - fraud: plein supérieur à la capacité du réservoir, plein sans kilomètres parcourus (carte carburant)
   - detour: trajet plus long que nécessaire
   - unknown: pas assez d'éléments
   Ajoute une note courte et factuelle en français qui cite les preuves.
3. Si une mission ou un détour est mentionné, compare les itinéraires (compare_routes) et donne un conseil de route.
Réponds à la fin UNIQUEMENT avec ce JSON:
{"anomalies": [{"kind": str, "probable_cause": "mechanical"|"behavior"|"fraud"|"detour"|"unknown", "note": str}],
 "route_advice": str, "manager_note_fr": str}
manager_note_fr = 2-3 lignes pour le responsable de flotte (anomalies, cause, action recommandée)."""


def _tools(state: State) -> list[Tool]:
    def get_fuel_stats(vehicle_id: str) -> dict:
        s = fuel_stats(state, vehicle_id)
        return {**s, "logs": s["logs"][-8:]}  # recent fills are enough for the model

    def get_vehicle(vehicle_id: str) -> dict:
        v = state.vehicles[vehicle_id]
        m = state.missions.get(v.mission_id or "")
        return {"vehicle": v.model_dump(), "mission": m.model_dump() if m else None}

    vid = {"type": "string"}
    return [
        Tool("get_fuel_stats", "Consommation attendue vs réelle sur 7 jours, derniers pleins et anomalies détectées.",
             {"type": "object", "properties": {"vehicle_id": vid}, "required": ["vehicle_id"]}, get_fuel_stats),
        Tool("get_vehicle", "Télémétrie (usure freins, codes défaut, ralenti 7j), kilométrage et mission du véhicule.",
             {"type": "object", "properties": {"vehicle_id": vid}, "required": ["vehicle_id"]}, get_vehicle),
        Tool("compare_routes", "Itinéraires plus court / moins cher / plus rapide entre deux villes (ids) pour un véhicule.",
             {"type": "object", "properties": {"from_city": {"type": "string"}, "to_city": {"type": "string"},
                                               "vehicle_id": vid}, "required": ["from_city", "to_city", "vehicle_id"]},
             lambda from_city, to_city, vehicle_id: compare_routes(state, from_city, to_city, vehicle_id)),
    ]


def depot_detour(state: State, vid: str, incident_id: str) -> dict | None:
    """Extra fuel + toll to drive from the nearest city to the incident's depot (cheapest route)."""
    inc = state.incidents.get(incident_id)
    if not inc or not inc.driver_instruction:
        return None
    v = state.vehicles[vid]
    start, depot_city = nearest_city(state, v.position.lat, v.position.lng), inc.driver_instruction.depot_city
    if start == depot_city:
        return {"from_city": start, "depot_city": depot_city, "km": 0, "fuel_l": 0, "fuel_cost_mad": 0, "toll_mad": 0}
    cheapest = next(r for r in compare_routes(state, start, depot_city, vid) if r.label == "cheapest")
    return {"from_city": start, "depot_city": depot_city, "km": cheapest.km, "fuel_l": cheapest.fuel_l,
            "fuel_cost_mad": cheapest.fuel_cost_mad, "toll_mad": cheapest.toll_mad, "path": cheapest.path}


def _merge(anomalies: list[FuelAnomaly], llm_items: list[dict]) -> None:
    by_kind = {i.get("kind"): i for i in llm_items if isinstance(i, dict)}
    for a in anomalies:
        item = by_kind.get(a.kind) or {}
        cause = item.get("probable_cause")
        a.probable_cause = cause if cause in CAUSES else "unknown"
        a.note = item.get("note") or a.note


async def run(event: dict, state: State) -> list[AgentEvent]:
    """event: {"vehicle_id", "tag", optional "incident_id"}. Stores anomalies in state.fuel_anomalies."""
    vid, incident_id = event["vehicle_id"], event.get("incident_id")
    events: list[AgentEvent] = []

    def emit(*args, **kw) -> AgentEvent:
        events.append(ev := state.emit(*args, **kw))
        return ev

    stats = fuel_stats(state, vid)
    anomalies: list[FuelAnomaly] = stats["anomalies"]
    for a in anomalies:
        emit("fuel", "alert", f"{vid}: {a.kind}", f"valeur {a.value} (seuil/attendu {a.expected}) le {a.detected_at}",
             vehicle_id=vid, anomaly_kind=a.kind)
    detour = depot_detour(state, vid, incident_id) if incident_id else None
    if detour:
        emit("fuel", "message", f"Détour vers le dépôt de {detour['depot_city']}",
             f"{detour['km']} km depuis {detour['from_city']}: {detour['fuel_l']} L de carburant "
             f"({detour['fuel_cost_mad']} MAD) + péage {detour['toll_mad']} MAD",
             vehicle_id=vid, incident_id=incident_id, **{k: x for k, x in detour.items() if k != "path"})

    if not anomalies and not detour:
        state.fuel_anomalies[vid] = []
        emit("fuel", "message", f"{vid}: consommation normale",
             f"{stats['actual_l_100km']} L/100km pour {stats['expected_l_100km']} attendus.", vehicle_id=vid)
        return events

    user = (f"Véhicule {vid}. Consommation attendue {stats['expected_l_100km']} L/100km, réelle 7j "
            f"{stats['actual_l_100km']} L/100km ({stats['delta_pct']}%). Anomalies détectées: "
            f"{[a.model_dump(exclude={'probable_cause', 'note'}) for a in anomalies]}.")
    if detour:
        user += (f" Le véhicule est en panne (incident {incident_id}) et doit rejoindre le dépôt de "
                 f"{detour['depot_city']}: surcoût du détour {detour}. Intègre-le dans le conseil de route.")
    out = await run_agent(tag=event["tag"], agent="fuel", system=SYSTEM, user=user, tools=_tools(state),
                          emit=emit, vehicle_id=vid)

    _merge(anomalies, out.get("anomalies") or [])
    state.fuel_anomalies[vid] = anomalies
    emit("fuel", "decision", f"{vid}: analyse carburant", out.get("manager_note_fr", ""), vehicle_id=vid,
         route_advice=out.get("route_advice", ""), causes={a.kind: a.probable_cause for a in anomalies},
         **({"incident_id": incident_id} if incident_id else {}))
    mech = [a for a in anomalies if a.probable_cause == "mechanical"]
    if mech:
        emit("fuel", "handoff", "→ Maintenance", mech[0].note or "Surconsommation d'origine mécanique probable.",
             vehicle_id=vid)
    return events
