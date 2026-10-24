"""Supplier ranking on KPIs. Weights shift with urgency."""
from __future__ import annotations

from typing import Literal

from ..schemas import SupplierScore
from ..state import State

Urgency = Literal["normal", "urgent", "critical"]

WEIGHTS: dict[str, dict[str, float]] = {
    "normal": {"price": 0.35, "delivery": 0.20, "on_time": 0.15, "warranty": 0.15, "rating": 0.15},
    "urgent": {"price": 0.20, "delivery": 0.40, "on_time": 0.20, "warranty": 0.10, "rating": 0.10},
    "critical": {"price": 0.10, "delivery": 0.50, "on_time": 0.25, "warranty": 0.05, "rating": 0.10},
}


def _scale(x: float, lo: float, hi: float, invert: bool = False) -> float:
    if hi == lo:
        return 1.0
    v = (x - lo) / (hi - lo)
    return 1 - v if invert else v


def score_suppliers(state: State, part_id: str, urgency: Urgency = "normal",
                    vehicle_type: str | None = None) -> list[SupplierScore]:
    rows = [(s, o) for s in state.suppliers.values() for o in s.offers
            if o.part_id == part_id and (vehicle_type is None or vehicle_type in s.vehicle_types)]
    if not rows:
        return []
    w = WEIGHTS[urgency]
    rng = lambda f: (min(map(f, rows)), max(map(f, rows)))  # noqa: E731
    pr, dr, otr, war, rar = (rng(lambda r: r[1].price_mad), rng(lambda r: r[1].delivery_hours),
                             rng(lambda r: r[0].on_time_pct), rng(lambda r: r[1].warranty_months),
                             rng(lambda r: r[0].rating))
    out = []
    for s, o in rows:
        pts = {
            "price": w["price"] * _scale(o.price_mad, *pr, invert=True) * 100,
            "delivery": w["delivery"] * _scale(o.delivery_hours, *dr, invert=True) * 100,
            "on_time": w["on_time"] * _scale(s.on_time_pct, *otr) * 100,
            "warranty": w["warranty"] * _scale(o.warranty_months, *war) * 100,
            "rating": w["rating"] * _scale(s.rating, *rar) * 100,
        }
        out.append(SupplierScore(
            supplier_id=s.id, supplier_name=s.name, part_id=part_id, price_mad=o.price_mad,
            delivery_hours=o.delivery_hours, warranty_months=o.warranty_months, on_time_pct=s.on_time_pct,
            rating=s.rating, score=round(sum(pts.values()), 1), breakdown={k: round(v, 1) for k, v in pts.items()},
        ))
    return sorted(out, key=lambda x: -x.score)
