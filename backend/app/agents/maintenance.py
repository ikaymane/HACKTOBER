"""Maintenance & diagnostic agent.

LLM job: read telemetry + driver report, pick the failing part, decide repair vs replace, choose the
supplier and the depot, explain everything. Numbers (costs, ETAs, penalties, KPI scores) always come
from deterministic tools, never from the model.
"""
from __future__ import annotations

from datetime import datetime

from ..llm import Tool, run_agent
from ..schemas import Diagnosis, DriverInstruction, Incident, PenaltyRisk, RepairDecision
from ..state import State
from ..tools.depots import find_load_takeover, find_replacement
from ..tools.parts import lookup_parts
from ..tools.penalty import compute_penalty
from ..tools.suppliers import score_suppliers

LABOR_MAD_PER_HOUR = 350

SYSTEM = """Tu es l'agent Maintenance & Diagnostic d'une flotte marocaine (camions et ambulances).
Un véhicule vient de signaler un problème. Ta mission, en utilisant les outils (n'invente jamais un chiffre):
1. Lire la télémétrie et la mission (get_vehicle).
2. Identifier la pièce défaillante (lookup_parts) en croisant codes défaut OBD, capteurs et rapport du chauffeur.
   Donne une confiance réaliste et la gravité: ok | monitor | drive_to_depot | stop_now.
3. Décider RÉPARER ou REMPLACER: pièce réparable ? coût réparation vs pièce neuve + main d'oeuvre, kilométrage
   vs durée de vie typique, pièce critique pour la sécurité, immobilisation. Une pièce de sécurité usée au-delà
   de sa durée de vie se remplace.
4. Si remplacement: classer les fournisseurs (score_suppliers). urgency = critical pour une ambulance,
   urgent pour un camion en mission, normal sinon. Choisis un fournisseur et justifie (KPIs).
5. Envoyer le chauffeur au dépôt le plus pertinent (find_replacement) pour prendre un véhicule de remplacement
   du même type. Calcule la pénalité SLA (compute_penalty) avec l'ETA du remplacement, ou null si aucun.
6. Si un camion n'a pas de remplacement dans le SLA, cherche un autre camion sur la route qui peut reprendre
   la charge (find_load_takeover) et compare les options par la pénalité.
Réponds à la fin UNIQUEMENT avec ce JSON:
{"part_id": str, "confidence": float, "severity": str, "evidence": [str],
 "action": "repair"|"replace", "action_reason": str,
 "urgency": "normal"|"urgent"|"critical", "chosen_supplier_id": str|null, "supplier_reason": str|null,
 "depot_id": str|null, "replacement_vehicle_id": str|null, "driver_message": str,
 "takeover_vehicle_id": str|null, "penalty_reason": str, "mitigation": str|null,
 "report_fr": str}
report_fr = rapport clair pour le responsable de flotte (5-8 lignes): panne, décision, fournisseur, dépôt, coût, risque pénalité."""


def _tools(state: State) -> list[Tool]:
    def get_vehicle(vehicle_id: str) -> dict:
        v = state.vehicles[vehicle_id]
        m = state.missions.get(v.mission_id or "")
        return {"vehicle": v.model_dump(), "mission": m.model_dump() if m else None}

    def get_part(part_id: str) -> dict:
        return state.parts[part_id].model_dump()

    return [
        Tool("get_vehicle", "Télémétrie, kilométrage, position et mission en cours du véhicule.",
             {"type": "object", "properties": {"vehicle_id": {"type": "string"}}, "required": ["vehicle_id"]}, get_vehicle),
        Tool("lookup_parts", "Pièces candidates à partir des codes défaut et des symptômes décrits.",
             {"type": "object", "properties": {"dtc": {"type": "array", "items": {"type": "string"}},
                                               "symptoms_text": {"type": "string"}}, "required": ["dtc"]},
             lambda dtc, symptoms_text="": lookup_parts(state, dtc, symptoms_text)),
        Tool("get_part", "Fiche complète d'une pièce du catalogue.",
             {"type": "object", "properties": {"part_id": {"type": "string"}}, "required": ["part_id"]}, get_part),
        Tool("score_suppliers", "Classement des fournisseurs pour une pièce (prix, délai, ponctualité, garantie, note).",
             {"type": "object", "properties": {"part_id": {"type": "string"},
                                               "urgency": {"type": "string", "enum": ["normal", "urgent", "critical"]},
                                               "vehicle_type": {"type": "string", "enum": ["truck", "ambulance"]}},
              "required": ["part_id", "urgency"]},
             lambda part_id, urgency, vehicle_type=None: score_suppliers(state, part_id, urgency, vehicle_type)[:4]),
        Tool("find_replacement", "Dépôts triés par distance avec véhicules de remplacement du même type et ETA.",
             {"type": "object", "properties": {"vehicle_id": {"type": "string"}}, "required": ["vehicle_id"]},
             lambda vehicle_id: find_replacement(state, vehicle_id)[:4]),
        Tool("compute_penalty", "Pénalité SLA. replacement_eta_min=null si aucun véhicule de remplacement.",
             {"type": "object", "properties": {"mission_id": {"type": "string"},
                                               "replacement_eta_min": {"type": ["number", "null"]}},
              "required": ["mission_id", "replacement_eta_min"]},
             lambda mission_id, replacement_eta_min=None: compute_penalty(state, mission_id, replacement_eta_min)),
        Tool("find_load_takeover", "Autres camions en mission vers la même destination avec de la place pour la charge.",
             {"type": "object", "properties": {"vehicle_id": {"type": "string"}}, "required": ["vehicle_id"]},
             lambda vehicle_id: find_load_takeover(state, vehicle_id)),
    ]


async def run(event: dict, state: State) -> Incident:
    """event: {"vehicle_id", "driver_report", "tag"}. Returns the Incident (also stored in state)."""
    vid = event["vehicle_id"]
    v = state.vehicles[vid]
    user = (f"Véhicule {vid} ({v.type}, {v.model}, {v.km} km). Codes défaut: {v.telemetry.dtc}. "
            f"Rapport chauffeur: \"{event.get('driver_report', '')}\". Diagnostique et décide.")
    out = await run_agent(tag=event["tag"], agent="maintenance", system=SYSTEM, user=user,
                          tools=_tools(state), emit=state.emit, vehicle_id=vid)
    inc = build_incident(state, vid, out)
    state.incidents[inc.id] = inc
    state.emit("maintenance", "decision", f"{inc.diagnosis.part_name}: {inc.decision.action}",
               inc.decision.reason, vehicle_id=vid, incident_id=inc.id, zone=inc.diagnosis.zone)
    return inc


def build_incident(state: State, vid: str, out: dict) -> Incident:
    """Turn the LLM's choices into an Incident; recompute every number from tools."""
    v = state.vehicles[vid]
    part = state.parts.get(out.get("part_id", "")) or state.parts[
        lookup_parts(state, v.telemetry.dtc)[0]["part_id"]]
    action = out.get("action") if out.get("action") in ("repair", "replace") else "replace"
    if action == "repair" and not part.repairable:
        action = "replace"

    suppliers = score_suppliers(state, part.id, out.get("urgency", "urgent"), v.type)
    chosen = next((s for s in suppliers if s.supplier_id == out.get("chosen_supplier_id")),
                  suppliers[0] if suppliers else None)
    if action == "repair":
        cost, downtime = part.repair_cost_mad, part.repair_hours
    else:
        cost = (chosen.price_mad if chosen else 0) + round(part.replace_labor_hours * LABOR_MAD_PER_HOUR)
        downtime = (chosen.delivery_hours if chosen else 24) + part.replace_labor_hours

    depots = {d["depot_id"]: d for d in find_replacement(state, vid)}
    d = depots.get(out.get("depot_id") or "")
    repl = out.get("replacement_vehicle_id")
    if d and repl not in d["spare_vehicles_same_type"]:
        repl = d["spare_vehicles_same_type"][0] if d["spare_vehicles_same_type"] else None
    instruction = DriverInstruction(
        depot_id=d["depot_id"], depot_city=state.depots[d["depot_id"]].city, distance_km=d["distance_km"],
        eta_min=d["eta_min"], replacement_vehicle_id=repl, message=out.get("driver_message", ""),
    ) if d else None

    takeover = out.get("takeover_vehicle_id")
    if takeover and not repl:  # another truck absorbs the load: penalty avoided
        avoided = compute_penalty(state, v.mission_id, None)["amount_mad"]
        pen = {"at_risk": False, "amount_mad": 0,
               "reason": f"Pénalité évitée ({avoided} MAD) grâce à la reprise de charge par {takeover}."}
    else:
        pen = compute_penalty(state, v.mission_id, d["eta_min"] if (d and repl) else None)

    return Incident(
        id=f"INC-{len(state.incidents) + 1:03d}", vehicle_id=vid, mission_id=v.mission_id,
        created_at=datetime.now().isoformat(timespec="seconds"),
        diagnosis=Diagnosis(part_id=part.id, part_name=part.name_fr, zone=part.zone,
                            confidence=float(out.get("confidence", 0.7)), severity=out.get("severity", "drive_to_depot"),
                            evidence=out.get("evidence") or v.telemetry.dtc),
        decision=RepairDecision(action=action, reason=out.get("action_reason", ""), cost_mad=cost,
                                downtime_hours=round(downtime, 1)),
        suppliers=suppliers, chosen_supplier_id=chosen.supplier_id if chosen else None,
        supplier_reason=out.get("supplier_reason"), driver_instruction=instruction,
        takeover_vehicle_id=takeover if (takeover and not repl and takeover in state.vehicles) else None,
        penalty=PenaltyRisk(at_risk=pen["at_risk"], amount_mad=pen["amount_mad"],
                            reason=out.get("penalty_reason") or pen["reason"],
                            mitigation=out.get("mitigation") or (f"Reprise de la charge par {takeover}" if takeover else None)),
        report_fr=out.get("report_fr", ""),
    )
