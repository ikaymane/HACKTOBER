"""Dev B tests: routing, seeded fuel anomalies, delay ETA after the scenario 2 takeover, scenario 3 timeline."""
import asyncio
import json
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import llm, routes_fuel
from app.agents import delay, orchestrator
from app.state import State
from app.tools.fuel_stats import fuel_stats
from app.tools.routing import compare_routes, mission_path


@pytest.fixture
def state():
    return State()


def kinds(state, vid):
    return {a.kind for a in fuel_stats(state, vid)["anomalies"]}


# ---------- routing ----------

def test_three_options_and_labels(state):
    opts = compare_routes(state, "casablanca", "fes", "T-12")
    assert [o.label for o in opts] == ["shortest", "cheapest", "fastest"]
    assert opts[0].path[0] == "casablanca" and opts[0].path[-1] == "fes"
    assert opts[0].km == min(o.km for o in opts)
    assert opts[1].total_cost_mad == min(o.total_cost_mad for o in opts)
    assert opts[2].hours == min(o.hours for o in opts)


def test_cheapest_differs_from_shortest_when_tolls_dominate(state):
    # Casablanca -> Fès: for the seeded numbers the highway wins on all three criteria (driver time
    # outweighs the toll saved), so use Settat -> Safi where the free national road is cheaper.
    short, cheap, _ = compare_routes(state, "settat", "safi", "T-12")
    assert cheap.path != short.path and cheap.total_cost_mad < short.total_cost_mad and cheap.toll_mad < short.toll_mad


def test_truck_pays_toll_multiplier_ambulance_does_not(state):
    truck = compare_routes(state, "casablanca", "rabat", "T-12")[0]
    amb = compare_routes(state, "casablanca", "rabat", "A-01")[0]
    mult = state.road_graph["meta"]["truck_toll_multiplier"]
    assert truck.toll_mad == round(23 * mult) and amb.toll_mad == 23


def test_unknown_city_raises(state):
    with pytest.raises(ValueError):
        compare_routes(state, "casablanca", "atlantis", "T-12")


def test_mission_path(state):
    p = mission_path(state, "M-112")  # casablanca -> meknes -> fes
    assert p["path"][0] == "casablanca" and p["path"][-1] == "fes" and "meknes" in p["path"]
    assert len(p["coords"]) == len(p["path"]) and 0 <= p["progress_pct"] <= 100


# ---------- fuel anomalies (seeded truth) ----------

def test_t12_overconsumption_about_22_percent(state):
    s = fuel_stats(state, "T-12")
    assert 18 <= s["delta_pct"] <= 26
    assert kinds(state, "T-12") == {"overconsumption"}


def test_t05_fuel_card_fraud(state):
    anomalies = fuel_stats(state, "T-05")["anomalies"]
    assert {a.kind for a in anomalies} == {"fill_over_capacity", "fill_without_km"}
    over = next(a for a in anomalies if a.kind == "fill_over_capacity")
    assert over.value == 455 and over.expected == 400
    assert next(a for a in anomalies if a.kind == "fill_without_km").value == 0


def test_t09_excessive_idle(state):
    assert "excessive_idle" in kinds(state, "T-09")
    assert next(a for a in fuel_stats(state, "T-09")["anomalies"] if a.kind == "excessive_idle").value == 31



def test_every_other_vehicle_is_clean(state):
    seeded = {"T-12": {"overconsumption"}, "T-05": {"fill_over_capacity", "fill_without_km"},
              "T-09": {"excessive_idle"}}
    for vid in state.vehicles:
        assert kinds(state, vid) == seeded.get(vid, set()), vid


def test_other_vehicles_have_no_consumption_idle_or_card_anomalies(state):
    for vid in state.vehicles:
        if vid not in ("T-12", "T-05", "T-09"):
            assert not kinds(state, vid) & {"overconsumption", "fill_without_km", "excessive_idle"}, vid


def test_log_rows_have_contract_fields(state):
    row = fuel_stats(state, "T-12")["logs"][1]
    assert set(row) == {"ts", "litres", "odometer_km", "l_100km", "station_city", "cost_mad"}


# ---------- REST ----------

def test_rest_routes(state, monkeypatch):
    monkeypatch.setattr(routes_fuel, "state", state)
    app = FastAPI()
    app.include_router(routes_fuel.router)
    c = TestClient(app)
    assert len(c.get("/cities").json()) == 15 + 1
    summary = c.get("/fuel/summary").json()
    assert len(summary) == len(state.vehicles) and set(summary[0]) == {
        "vehicle_id", "expected_l_100km", "actual_l_100km", "delta_pct", "anomalies"}
    assert c.get("/fuel/T-12").json()["delta_pct"] > 15
    assert c.get("/fuel/nope").status_code == 404
    r = c.post("/route/compare", json={"from": "casablanca", "to": "fes", "vehicle_id": "T-12"}).json()
    assert [o["label"] for o in r] == ["shortest", "cheapest", "fastest"]
    assert c.post("/route/compare", json={"from": "casablanca", "to": "xx", "vehicle_id": "T-12"}).status_code == 404
    assert c.get("/missions/M-112/path").json()["path"][0] == "casablanca"
    assert c.get("/missions/M-112/eta").json()["stops"][0]["city"] == "meknes"
    assert c.get("/missions/nope/eta").status_code == 404


# ---------- agents, offline with a scripted LLM ----------

def _call(i, name, args):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _script(tmp_path, tag, *msgs):
    (tmp_path / f"{tag}.json").write_text(json.dumps([
        {"role": "assistant", "content": m} if isinstance(m, str) else {"role": "assistant", "content": "", "tool_calls": m}
        for m in msgs]))


def _maintenance(part, **kw):
    base = {"part_id": part, "confidence": 0.8, "severity": "drive_to_depot", "evidence": ["x"], "action": "replace",
            "action_reason": "usure", "urgency": "urgent", "chosen_supplier_id": None, "supplier_reason": None,
            "depot_id": None, "replacement_vehicle_id": None, "driver_message": "Rejoignez le dépôt.",
            "takeover_vehicle_id": None, "penalty_reason": "", "mitigation": None, "report_fr": "Rapport."}
    return json.dumps({**base, **kw})


ORCH = json.dumps({"priority": "high", "summary_fr": "ok", "next_actions": ["a"], "client_message_fr": "Retard"})


def test_scenario2_delay_eta_via_t03(state, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setenv("REPLAY", "1")
    _script(tmp_path, "s2-maintenance", [_call(1, "get_vehicle", {"vehicle_id": "T-07"})],
            _maintenance("P-WPUMP", severity="stop_now", depot_id="DEP-SETTAT", takeover_vehicle_id="T-03"))
    _script(tmp_path, "s2-delay", [_call(1, "get_mission", {"mission_id": "M-107"})],
            json.dumps({"stop_order": ["marrakech"], "client_message_fr": "Pharma Sud: livraison par T-03 vers 10h.",
                        "summary_fr": "T-03 livre Marrakech."}))
    _script(tmp_path, "s2-fuel", json.dumps({"anomalies": [], "route_advice": "Route nationale.", "manager_note_fr": "RAS"}))
    _script(tmp_path, "s2-orchestrator", ORCH)
    asyncio.run(orchestrator.handle_scenario(state.scenarios[2], state))

    eta = state.etas["M-107"]
    assert state.missions["M-107"].vehicle_id == "T-03"
    stop = eta["stops"][0]
    assert stop["city"] == "marrakech" and "Pharma" in eta["client_message_fr"]
    # 08:00 + (T-03 -> T-07 at 70 km/h + 30 min transfer) + drive to Marrakech with T-03
    assert 30 < eta["start_delay_min"] < 120
    assert datetime.fromisoformat(stop["eta"]) > datetime(2026, 10, 24, 8, 0)
    assert stop["late_min"] == max(0, round((datetime.fromisoformat(stop["eta"])
                                             - datetime.fromisoformat("2026-10-24T12:30")).total_seconds() / 60))
    decisions = [e for e in state.audit if e.agent == "delay" and e.kind == "decision"]
    assert decisions and decisions[0].data["stops"] == eta["stops"]
    assert state.fuel_anomalies["T-07"] == []


def test_delay_ignores_bad_stop_order_and_reports_lateness(state, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setenv("REPLAY", "1")
    state.missions["M-105"].stops[0].window_end = "2026-10-24T08:10"  # make the first stop late
    inc = _fake_incident(state, "T-05", "M-105", eta_min=90)
    _script(tmp_path, "t-delay", json.dumps({"stop_order": ["paris"], "client_message_fr": "Retard.", "summary_fr": "s"}))
    asyncio.run(delay.run({"mission_id": "M-105", "incident_id": inc.id, "vehicle_id": "T-05", "tag": "t-delay"}, state))
    stops = state.etas["M-105"]["stops"]
    assert [s["city"] for s in stops] == ["eljadida", "safi"]  # invalid order falls back to the original
    assert stops[0]["eta"] == "2026-10-24T09:30" and stops[0]["late_min"] == 80  # 90 min delay, already in El Jadida


def _fake_incident(state, vid, mid, eta_min):
    from app.schemas import Diagnosis, DriverInstruction, Incident, PenaltyRisk, RepairDecision
    inc = Incident(
        id="INC-T", vehicle_id=vid, mission_id=mid, created_at="2026-10-24T08:00",
        diagnosis=Diagnosis(part_id="P", part_name="p", zone="engine", confidence=1, severity="ok", evidence=[]),
        decision=RepairDecision(action="repair", reason="", cost_mad=0, downtime_hours=0),
        driver_instruction=DriverInstruction(depot_id="DEP-CASA", depot_city="casablanca", distance_km=1, eta_min=eta_min,
                                             replacement_vehicle_id="T-11", message=""),
        penalty=PenaltyRisk(at_risk=False, amount_mad=0, reason=""), report_fr="")
    state.incidents[inc.id] = inc
    state.missions[mid].vehicle_id = "T-11"
    return inc


def test_scenario3_timeline_fuel_handoff_maintenance_orchestrator(state, tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setenv("REPLAY", "1")
    note = "Surconsommation de 21% avec freins usés à 84% et code C0040: étrier de frein qui traîne."
    _script(tmp_path, "s3-fuel", [_call(1, "get_fuel_stats", {"vehicle_id": "T-12"}), _call(2, "get_vehicle", {"vehicle_id": "T-12"})],
            json.dumps({"anomalies": [{"kind": "overconsumption", "probable_cause": "mechanical", "note": note}],
                        "route_advice": "Garder l'autoroute.", "manager_note_fr": "Étrier à contrôler."}))
    _script(tmp_path, "s3-maintenance", [_call(1, "get_vehicle", {"vehicle_id": "T-12"})],
            _maintenance("P-BCAL", action="repair", depot_id="DEP-CASA", replacement_vehicle_id="T-11"))
    _script(tmp_path, "s3-delay", json.dumps({"stop_order": ["meknes", "fes"], "client_message_fr": "Fès Textile: léger retard.",
                                              "summary_fr": "ok"}))
    _script(tmp_path, "s3-orchestrator", ORCH)
    asyncio.run(orchestrator.handle_scenario(state.scenarios[3], state))

    a = state.fuel_anomalies["T-12"]
    assert [x.kind for x in a] == ["overconsumption"] and a[0].probable_cause == "mechanical" and a[0].note == note
    assert fuel_stats(state, "T-12")["anomalies"][0].note == note  # GET /fuel/T-12 keeps the LLM note

    steps = [(e.agent, e.kind) for e in state.audit if e.kind in ("alert", "handoff", "decision")]
    order = [steps.index(x) for x in (("fuel", "alert"), ("fuel", "handoff"), ("maintenance", "decision"),
                                      ("orchestrator", "decision"))]
    assert order == sorted(order)
    assert any(e.agent == "delay" and e.kind == "decision" for e in state.audit)


def test_fleet_fuel_kpi_comes_from_the_logs(state):
    from app.tools.fuel_stats import fleet_fuel_kpi
    kpi = fleet_fuel_kpi(state)
    assert kpi["spend_mad"] > kpi["overspend_mad"] > 0
    assert kpi["anomalies"] == sum(len(fuel_stats(state, v)["anomalies"]) for v in state.vehicles)
    assert fleet_fuel_kpi(state) == kpi  # no clock in it
