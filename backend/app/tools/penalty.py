"""SLA penalty: the company must put a replacement vehicle on the road within the mission SLA."""
from __future__ import annotations

from typing import Optional

from ..state import State


def compute_penalty(state: State, mission_id: Optional[str], replacement_eta_min: Optional[float]) -> dict:
    """replacement_eta_min=None means no replacement vehicle at all."""
    m = state.missions.get(mission_id or "")
    if not m:
        return {"at_risk": False, "amount_mad": 0, "reason": "Aucune mission en cours."}
    if replacement_eta_min is None:
        return {"at_risk": True, "amount_mad": m.penalty_flat_mad,
                "reason": f"Aucun véhicule de remplacement disponible: pénalité forfaitaire contrat {m.client}.",
                "sla_minutes": m.sla_minutes_replacement}
    late = replacement_eta_min - m.sla_minutes_replacement
    if late <= 0:
        return {"at_risk": False, "amount_mad": 0, "sla_minutes": m.sla_minutes_replacement,
                "reason": f"Remplacement en {round(replacement_eta_min)} min, SLA {m.sla_minutes_replacement} min respecté."}
    amount = round(late / 60 * m.penalty_mad_per_hour)
    return {"at_risk": True, "amount_mad": amount, "sla_minutes": m.sla_minutes_replacement,
            "reason": f"Remplacement en {round(replacement_eta_min)} min > SLA {m.sla_minutes_replacement} min "
                      f"({round(late)} min de retard x {m.penalty_mad_per_hour} MAD/h)."}
