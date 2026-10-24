"""Orchestrator: routes a scenario through the agents, applies fleet changes, writes the final decision.

Fuel and Delay agents (Dev B) are optional imports: if agents/fuel.py or agents/delay.py are not merged
yet, the orchestrator skips them and says so on the timeline.
"""
from __future__ import annotations

import importlib
import json

from ..llm import run_agent
from ..schemas import Incident
from ..state import State
from . import maintenance

SYSTEM = """Tu es l'orchestrateur d'une flotte marocaine. Tu reçois le rapport de l'agent Maintenance et les
résultats des agents Carburant et Retards. Arbitre et produis la décision finale pour le responsable de flotte.
Réponds UNIQUEMENT avec ce JSON:
{"priority": "low"|"medium"|"high", "summary_fr": str (3-4 lignes), "next_actions": [str] (3-5 actions concrètes),
 "client_message_fr": str|null (message court au client si la livraison/le transfert est impacté)}"""


def _optional_agent(name: str):
    try:
        return importlib.import_module(f"app.agents.{name}")
    except ModuleNotFoundError:
        return None


async def _call_optional(name: str, event: dict, state: State, vid: str) -> bool:
    mod = _optional_agent(name)
    if not mod or not hasattr(mod, "run"):
        state.emit("orchestrator", "message", f"Agent {name} non branché", "En attente du merge Dev B.", vehicle_id=vid)
        return False
    state.emit("orchestrator", "handoff", f"→ agent {name}", json.dumps(event, ensure_ascii=False), vehicle_id=vid)
    await mod.run(event, state)
    return True


def apply_incident(state: State, inc: Incident) -> None:
    """Fleet side effects: broken vehicle out, replacement vehicle or takeover truck gets the mission."""
    v = state.vehicles[inc.vehicle_id]
    v.status = "breakdown"
    mission = state.missions.get(inc.mission_id or "")
    di = inc.driver_instruction
    if di and di.replacement_vehicle_id:
        repl = state.vehicles[di.replacement_vehicle_id]
        depot = state.depots[di.depot_id]
        if repl.id in depot.spare_vehicles:
            depot.spare_vehicles.remove(repl.id)
        repl.status = "on_mission"
        if mission:
            repl.mission_id, mission.vehicle_id = mission.id, repl.id
        v.mission_id = None
        state.emit("orchestrator", "handoff", f"{repl.id} remplace {v.id}",
                   f"Départ {depot.city}, ETA {di.eta_min} min", vehicle_id=repl.id, incident_id=inc.id)
    elif mission and inc.takeover_vehicle_id:
        mission.vehicle_id = inc.takeover_vehicle_id  # delay agent now tracks the takeover truck
        v.mission_id = None
        state.emit("orchestrator", "handoff", f"{inc.takeover_vehicle_id} reprend la charge de {v.id}",
                   inc.penalty.mitigation or "", vehicle_id=inc.takeover_vehicle_id, incident_id=inc.id)


async def handle_scenario(sc: dict, state: State) -> None:
    vid, tag = sc["vehicle_id"], f"s{sc['id']}"

    fuel_ran = False
    if sc.get("expected", {}).get("fuel_anomaly"):  # fuel-led scenario: fuel agent spots it first
        fuel_ran = await _call_optional("fuel", {"vehicle_id": vid, "tag": f"{tag}-fuel"}, state, vid)
        state.emit("orchestrator", "handoff", "Carburant → Maintenance",
                   "Surconsommation avec signal mécanique: diagnostic demandé.", vehicle_id=vid)

    inc = await maintenance.run({"vehicle_id": vid, "driver_report": sc["driver_report"], "tag": f"{tag}-maintenance"}, state)
    apply_incident(state, inc)

    if inc.mission_id:
        await _call_optional("delay", {"mission_id": inc.mission_id, "incident_id": inc.id, "vehicle_id": vid,
                                       "tag": f"{tag}-delay"}, state, vid)
    if not fuel_ran:
        await _call_optional("fuel", {"vehicle_id": vid, "incident_id": inc.id, "tag": f"{tag}-fuel"}, state, vid)

    timeline = [f"[{e.agent}] {e.title}: {e.detail[:200]}" for e in state.audit
                if e.vehicle_id in (vid, None) and e.kind in ("decision", "alert", "handoff")][-15:]
    user = (f"Incident:\n{inc.model_dump_json(exclude={'suppliers'})}\n\n"
            f"Fournisseur retenu: {inc.chosen_supplier_id}\nTimeline:\n" + "\n".join(timeline))
    out = await run_agent(tag=f"{tag}-orchestrator", agent="orchestrator", system=SYSTEM, user=user,
                          tools=[], emit=state.emit, vehicle_id=vid)
    state.emit("orchestrator", "decision", f"Décision finale ({out.get('priority', 'medium')})",
               out.get("summary_fr", ""), vehicle_id=vid, incident_id=inc.id,
               next_actions=out.get("next_actions", []), client_message_fr=out.get("client_message_fr"))
