"""Parts catalog lookup: fault codes + driver words -> candidate failing parts."""
from __future__ import annotations

import re
import unicodedata

from ..state import State


def _norm(s: str) -> set[str]:
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{4,}", s)}


def lookup_parts(state: State, dtc: list[str], symptoms_text: str = "") -> list[dict]:
    words = _norm(symptoms_text)
    out = []
    for p in state.parts.values():
        dtc_hits = sorted(set(dtc) & set(p.dtc_codes))
        sym_hits = [s for s in p.symptoms if _norm(s) & words]
        score = 3 * len(dtc_hits) + len(sym_hits)
        if score:
            out.append({
                "part_id": p.id, "name": p.name_fr, "zone": p.zone, "match_score": score,
                "dtc_matched": dtc_hits, "symptoms_matched": sym_hits,
                "safety_critical": p.safety_critical, "repairable": p.repairable,
                "repair_cost_mad": p.repair_cost_mad, "repair_hours": p.repair_hours,
                "replace_labor_hours": p.replace_labor_hours, "typical_life_km": p.typical_life_km,
            })
    return sorted(out, key=lambda x: -x["match_score"])[:5]
