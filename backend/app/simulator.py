"""Scenario runner: injects scripted telemetry, then hands off to the orchestrator.

Until the real agents land, `_mock_pipeline` emits a fake event stream + Incident that follows
shared/contracts.md exactly, so the frontend can be built against it right now.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from .schemas import Diagnosis, DriverInstruction, Incident, PenaltyRisk, RepairDecision
from .state import State

USE_MOCK = True  # Dev A: flip to False when agents/orchestrator.py is wired


async def run_scenario(scenario_id: int, state: State) -> None:
    sc = state.scenarios[scenario_id]
    v = state.vehicles[sc["vehicle_id"]]
    v.telemetry = v.telemetry.model_copy(update=sc["telemetry"])
    v.status = "breakdown"
    state.emit("system", "alert", sc["title"], sc["driver_report"], vehicle_id=v.id, scenario_id=scenario_id)

    if USE_MOCK:
        await _mock_pipeline(sc, state)
    else:
        from .agents import orchestrator  # noqa: PLC0415

        await orchestrator.handle_scenario(sc, state)


async def _mock_pipeline(sc: dict, state: State) -> None:
    v = state.vehicles[sc["vehicle_id"]]
    exp = sc["expected"]
    part = state.parts[exp["part_id"]]
    step = lambda: asyncio.sleep(0.6)  # noqa: E731

    state.emit("maintenance", "tool_call", "get_telemetry", vehicle_id=v.id, args={"vehicle_id": v.id}); await step()
    state.emit("maintenance", "tool_result", "Télémétrie reçue", str(v.telemetry.model_dump()), vehicle_id=v.id); await step()
    state.emit("maintenance", "tool_call", "lookup_parts", vehicle_id=v.id, args={"dtc": v.telemetry.dtc}); await step()
    state.emit("maintenance", "thought", f"Diagnostic: {part.name_fr}", "[MOCK] raisonnement LLM ici", vehicle_id=v.id); await step()

    inc_id = f"INC-{len(state.incidents) + 1:03d}"
    mission = state.missions.get(v.mission_id) if v.mission_id else None
    depot = state.depots.get(exp.get("depot") or "")
    state.incidents[inc_id] = Incident(
        id=inc_id, vehicle_id=v.id, mission_id=v.mission_id, created_at=datetime.now().isoformat(timespec="seconds"),
        diagnosis=Diagnosis(part_id=part.id, part_name=part.name_fr, zone=part.zone, confidence=0.82,
                            severity="drive_to_depot", evidence=v.telemetry.dtc + [sc["driver_report"]]),
        decision=RepairDecision(action="replace", reason="[MOCK]", cost_mad=4200, downtime_hours=6),
        driver_instruction=DriverInstruction(
            depot_id=depot.id, depot_city=depot.city, distance_km=62, eta_min=45,
            replacement_vehicle_id=exp.get("replacement"), message="[MOCK] Rejoignez le dépôt.") if depot else None,
        penalty=PenaltyRisk(at_risk=exp.get("penalty", False),
                            amount_mad=mission.penalty_flat_mad if (mission and exp.get("penalty")) else 0,
                            reason="[MOCK]", mitigation=exp.get("mitigation_vehicle")),
        report_fr="[MOCK] Rapport d'incident.",
    )
    state.emit("maintenance", "decision", f"Incident {inc_id} déclaré", vehicle_id=v.id, incident_id=inc_id); await step()
    state.emit("orchestrator", "handoff", "→ delay + fuel", vehicle_id=v.id); await step()
    state.emit("orchestrator", "decision", "[MOCK] Plan final", vehicle_id=v.id, incident_id=inc_id)
