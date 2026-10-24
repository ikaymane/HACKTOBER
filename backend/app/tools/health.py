"""Per-zone health of a vehicle, for the 3D exploded view (green / orange / red parts)."""
from __future__ import annotations

from ..state import State

ZONES = ["engine", "cooling", "electrical", "brakes", "transmission", "tires", "fuel"]


def vehicle_health(state: State, vehicle_id: str) -> dict:
    v = state.vehicles[vehicle_id]
    t = v.telemetry
    zones = {z: {"status": "ok", "reasons": [], "part_id": None, "incident_id": None} for z in ZONES}

    def flag(zone: str, status: str, reason: str) -> None:
        z = zones[zone]
        if status == "fail" or z["status"] == "ok":
            z["status"] = status
        z["reasons"].append(reason)

    if t.coolant_c > 105: flag("cooling", "fail", f"Liquide {t.coolant_c}°C")
    elif t.coolant_c > 98: flag("cooling", "warn", f"Liquide {t.coolant_c}°C")
    if t.battery_v < 12.0: flag("electrical", "fail", f"Tension {t.battery_v} V")
    elif t.battery_v < 13.2: flag("electrical", "warn", f"Tension {t.battery_v} V")
    if t.oil_bar < 1.5: flag("engine", "fail", f"Pression huile {t.oil_bar} bar")
    elif t.oil_bar < 2.5: flag("engine", "warn", f"Pression huile {t.oil_bar} bar")
    if t.brake_wear_pct > 85: flag("brakes", "fail", f"Usure freins {t.brake_wear_pct}%")
    elif t.brake_wear_pct > 70: flag("brakes", "warn", f"Usure freins {t.brake_wear_pct}%")
    if t.idle_pct_7d > 25: flag("fuel", "warn", f"Ralenti {t.idle_pct_7d}% (7j)")
    for code in t.dtc:
        for p in state.parts.values():
            if code in p.dtc_codes:
                flag(p.zone, "warn", f"Code {code}")
                break

    for inc in state.incidents.values():  # agent diagnosis wins
        if inc.vehicle_id == vehicle_id:
            z = zones[inc.diagnosis.zone]
            z.update(status="fail", part_id=inc.diagnosis.part_id, incident_id=inc.id)
            z["reasons"].insert(0, f"Diagnostic agent: {inc.diagnosis.part_name}")
    return {"vehicle_id": vehicle_id, "type": v.type, "zones": zones}
