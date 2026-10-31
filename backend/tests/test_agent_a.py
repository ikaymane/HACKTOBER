"""Dev A tests: deterministic tools + full scenario 2 offline with a scripted (replayed) LLM."""
import asyncio
import json

import pytest

from app import llm
from app.agents import orchestrator
from app.state import State
from app.tools.depots import find_load_takeover, find_replacement
from app.tools.health import vehicle_health
from app.tools.parts import lookup_parts
from app.tools.penalty import compute_penalty
from app.tools.suppliers import score_suppliers


@pytest.fixture
def state():
    return State()


def test_lookup_parts_alternator(state):
    assert lookup_parts(state, ["P0562"], "voyant batterie, tension basse")[0]["part_id"] == "P-ALT"


def test_suppliers_ambulance_critical_prefers_fast(state):
    ranked = score_suppliers(state, "P-ALT", "critical", "ambulance")
    assert ranked[0].delivery_hours == min(r.delivery_hours for r in ranked)


def test_truck_suppliers_exclude_ambulance_only(state):
    assert all(r.supplier_id != "SUP-MEDI" for r in score_suppliers(state, "P-WPUMP", "urgent", "truck"))


def test_scenario1_settat_has_spare_ambulance_within_sla(state):
    best = next(d for d in find_replacement(state, "A-03") if d["spare_vehicles_same_type"])
    assert best["depot_id"] == "DEP-SETTAT"
    assert not compute_penalty(state, "M-203", best["eta_min"])["at_risk"]


def test_scenario2_takeover_by_t03(state):
    assert find_load_takeover(state, "T-07")[0]["vehicle_id"] == "T-03"
    assert compute_penalty(state, "M-107", None)["amount_mad"] == 8000


def _call(i, name, args):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def test_scenario2_end_to_end_replay(state, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setenv("REPLAY", "1")
    final = {
        "part_id": "P-WPUMP", "confidence": 0.8, "severity": "stop_now", "evidence": ["P0217", "118°C"],
        "action": "replace", "action_reason": "487000 km > durée de vie", "urgency": "urgent",
        "chosen_supplier_id": "SUP-SAHARA", "supplier_reason": "Marrakech, rapide",
        "depot_id": "DEP-SETTAT", "replacement_vehicle_id": None, "driver_message": "Arrêtez-vous.",
        "takeover_vehicle_id": "T-03", "penalty_reason": "", "mitigation": "T-03 reprend 10 palettes",
        "report_fr": "Rapport.",
    }
    (tmp_path / "s2-maintenance.json").write_text(json.dumps([
        {"role": "assistant", "content": "", "tool_calls": [_call(1, "get_vehicle", {"vehicle_id": "T-07"})]},
        {"role": "assistant", "content": "", "tool_calls": [_call(2, "lookup_parts", {"dtc": ["P0217"]})]},
        {"role": "assistant", "content": "", "tool_calls": [_call(3, "find_load_takeover", {"vehicle_id": "T-07"})]},
        {"role": "assistant", "content": json.dumps(final)},
    ]))
    # Dev B agents run after maintenance (fuel/delay replays kept minimal here, covered in test_fuel_delay.py)
    (tmp_path / "s2-delay.json").write_text(json.dumps([
        {"role": "assistant", "content": json.dumps({"stop_order": ["marrakech"], "client_message_fr": "Retard", "summary_fr": "ok"})},
    ]))
    (tmp_path / "s2-fuel.json").write_text(json.dumps([
        {"role": "assistant", "content": json.dumps({"anomalies": [], "route_advice": "", "manager_note_fr": "RAS"})},
    ]))
    (tmp_path / "s2-orchestrator.json").write_text(json.dumps([
        {"role": "assistant", "content": json.dumps({"priority": "high", "summary_fr": "ok", "next_actions": ["a"],
                                                     "client_message_fr": "Retard"})},
    ]))
    asyncio.run(orchestrator.handle_scenario(state.scenarios[2], state))

    inc = next(iter(state.incidents.values()))
    assert inc.diagnosis.part_id == "P-WPUMP" and inc.decision.action == "replace"
    assert inc.chosen_supplier_id == "SUP-SAHARA" and inc.penalty.amount_mad == 0
    assert "8000" in inc.penalty.reason
    assert inc.takeover_vehicle_id == "T-03" and state.missions["M-107"].vehicle_id == "T-03"
    assert vehicle_health(state, "T-07")["zones"]["cooling"]["status"] == "fail"
    assert state.audit[-1].agent == "orchestrator" and state.audit[-1].kind == "decision"


def _replay_all(state, sid):
    """Runs a scenario on the recordings committed in replay_cache/, as `python run.py` does."""
    from app.simulator import run_scenario
    asyncio.run(run_scenario(sid, state))
    return list(state.incidents.values())[-1]


@pytest.mark.parametrize("sid,part,fleet_move", [(1, "P-ALT", "A-04"), (2, "P-WPUMP", "T-03"), (3, "P-BCAL", "T-10")])
def test_offline_demo_runs_on_committed_recordings(state, monkeypatch, sid, part, fleet_move):
    monkeypatch.setenv("REPLAY", "1")
    monkeypatch.delenv("MOCK", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    inc = _replay_all(state, sid)
    assert inc.diagnosis.part_id == part
    moved = inc.takeover_vehicle_id or inc.driver_instruction.replacement_vehicle_id
    assert moved == fleet_move
    titles = [e.title for e in state.audit]
    assert not any(e.title == "Erreur agent" for e in state.audit)
    assert not any("indisponible" in t for t in titles)
    assert any(t.startswith("Décision finale") for t in titles)


def test_takeover_reports_the_penalty_it_avoided(state, monkeypatch):
    monkeypatch.setenv("REPLAY", "1")
    monkeypatch.delenv("MOCK", raising=False)
    inc = _replay_all(state, 2)
    assert inc.penalty.avoided_mad == 8000
    assert not inc.penalty.at_risk


def test_side_agent_failure_keeps_the_final_decision(state, tmp_path, monkeypatch):
    monkeypatch.setenv("REPLAY", "1")
    monkeypatch.delenv("MOCK", raising=False)
    for name in ("s1-maintenance", "s1-orchestrator"):  # no fuel or delay recording
        (tmp_path / f"{name}.json").write_text((llm.CACHE / f"{name}.json").read_text("utf-8"), "utf-8")
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    _replay_all(state, 1)
    titles = [e.title for e in state.audit]
    assert "Agent delay indisponible" in titles and any(t.startswith("Décision finale") for t in titles)


def test_replaying_a_finished_scenario_is_refused(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.state import state as live_state
    monkeypatch.setenv("REPLAY", "1")
    live_state.reset()
    with TestClient(app) as c:
        live_state.vehicles["T-07"].status = "breakdown"
        assert c.post("/api/scenario/2").status_code == 409
        assert c.post("/api/reset").json() == {"ok": True}
    live_state.reset()


def test_approval_goes_on_the_audit_trail(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.state import state as live_state
    monkeypatch.setenv("REPLAY", "1")
    monkeypatch.delenv("MOCK", raising=False)
    live_state.reset()
    inc = _replay_all(live_state, 2)
    with TestClient(app) as c:
        assert c.post(f"/incidents/{inc.id}/approve").json()["approved"] is True
        c.post(f"/incidents/{inc.id}/approve")  # idempotent
    assert sum("approuvé" in e.title for e in live_state.audit) == 1
    live_state.reset()
