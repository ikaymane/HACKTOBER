"""Fuel consumption stats + anomaly detectors. Deterministic; the fuel agent (LLM) only explains the causes."""
from __future__ import annotations

from datetime import datetime, timedelta

from ..schemas import FuelAnomaly
from ..state import State

NOW = datetime(2026, 10, 24, 8, 0)  # sim clock, same as the seed data
WINDOW_DAYS = 7
OVERCONSUMPTION_PCT = 15
IDLE_PCT_LIMIT = 25
MIN_KM_BETWEEN_FILLS = 20
MIN_LITRES_NO_KM = 50


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="minutes")


def vehicle_logs(state: State, vehicle_id: str) -> list[dict]:
    """Fill-ups sorted by time, each with km since the previous fill, l_100km and cost_mad."""
    rows = sorted((f for f in state.fuel_logs if f["vehicle_id"] == vehicle_id), key=lambda f: f["ts"])
    out, prev_odo = [], None
    for f in rows:
        km = None if prev_odo is None else f["odometer_km"] - prev_odo
        out.append({"ts": f["ts"], "litres": f["litres"], "odometer_km": f["odometer_km"],
                    "l_100km": round(f["litres"] / km * 100, 1) if km and km > 0 else None,
                    "station_city": f["station_city"], "cost_mad": round(f["litres"] * f["price_mad_l"], 2),
                    "km_since_prev": km})
        prev_odo = f["odometer_km"]
    return out


def _detect(state: State, vid: str, logs: list[dict], actual: float | None, delta_pct: float | None) -> list[FuelAnomaly]:
    v = state.vehicles[vid]
    found: list[FuelAnomaly] = []
    if delta_pct is not None and delta_pct > OVERCONSUMPTION_PCT:
        found.append(FuelAnomaly(vehicle_id=vid, kind="overconsumption", value=delta_pct, expected=OVERCONSUMPTION_PCT,
                                 detected_at=_iso(NOW)))
    for f in logs:
        if f["litres"] > v.tank_l:
            found.append(FuelAnomaly(vehicle_id=vid, kind="fill_over_capacity", value=f["litres"], expected=v.tank_l,
                                     detected_at=f["ts"]))
        km = f["km_since_prev"]
        if km is not None and km < MIN_KM_BETWEEN_FILLS and f["litres"] > MIN_LITRES_NO_KM:
            found.append(FuelAnomaly(vehicle_id=vid, kind="fill_without_km", value=max(km, 0), expected=MIN_KM_BETWEEN_FILLS,
                                     detected_at=f["ts"]))
    if v.telemetry.idle_pct_7d > IDLE_PCT_LIMIT:
        found.append(FuelAnomaly(vehicle_id=vid, kind="excessive_idle", value=v.telemetry.idle_pct_7d,
                                 expected=IDLE_PCT_LIMIT, detected_at=_iso(NOW)))
    return found


def _is_suspect(f: dict, tank_l: float) -> bool:
    km = f["km_since_prev"]
    return f["litres"] > tank_l or (km is not None and km < MIN_KM_BETWEEN_FILLS and f["litres"] > MIN_LITRES_NO_KM)


def fuel_stats(state: State, vehicle_id: str) -> dict:
    v = state.vehicles[vehicle_id]
    logs = vehicle_logs(state, vehicle_id)
    since = _iso(NOW - timedelta(days=WINDOW_DAYS))
    # Fills flagged as over-capacity / no-km are fraud signals, not consumption: keep them out of the average.
    window = [f for f in logs if f["ts"] >= since and f["km_since_prev"] and f["km_since_prev"] > 0
              and not _is_suspect(f, v.tank_l)]
    km = sum(f["km_since_prev"] for f in window)
    actual = round(sum(f["litres"] for f in window) / km * 100, 1) if km else None
    delta = round((actual / v.base_l_100km - 1) * 100, 1) if actual else None

    anomalies = _detect(state, vehicle_id, logs, actual, delta)
    old = {a.kind: a for a in state.fuel_anomalies.get(vehicle_id, [])}  # keep LLM causes/notes already stored
    for a in anomalies:
        prev = old.get(a.kind)
        if prev and prev.value == a.value and prev.detected_at == a.detected_at:
            a.probable_cause, a.note = prev.probable_cause, prev.note
    return {"vehicle_id": vehicle_id, "expected_l_100km": v.base_l_100km, "actual_l_100km": actual,
            "delta_pct": delta, "logs": [{k: x for k, x in f.items() if k != "km_since_prev"} for f in logs],
            "anomalies": anomalies}


def fleet_fuel_kpi(state: State) -> dict:
    """Fleet totals over the window, from the fill-up logs only: they change when a fill-up does, not with time."""
    since = _iso(NOW - timedelta(days=WINDOW_DAYS))
    spend = overspend = 0.0
    flags: list[dict] = []
    for vid, v in state.vehicles.items():
        stats = fuel_stats(state, vid)
        flags += [{"vehicle_id": vid, "kind": a.kind} for a in stats["anomalies"]]
        logs = [f for f in vehicle_logs(state, vid) if f["ts"] >= since]
        spend += sum(f["cost_mad"] for f in logs)
        if (stats["delta_pct"] or 0) > 5:  # past normal variation: the extra litres cost real money
            used = [f for f in logs if f["km_since_prev"] and f["km_since_prev"] > 0 and not _is_suspect(f, v.tank_l)]
            km = sum(f["km_since_prev"] for f in used)
            litres = sum(f["litres"] for f in used)
            if litres:
                price = sum(f["cost_mad"] for f in used) / litres
                overspend += max(0.0, litres - km * v.base_l_100km / 100) * price
    return {"window_days": WINDOW_DAYS, "spend_mad": round(spend), "overspend_mad": round(overspend), "anomalies": len(flags), "flags": flags}
