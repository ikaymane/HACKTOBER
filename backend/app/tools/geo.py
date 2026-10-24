"""Distance helpers shared by tools."""
from __future__ import annotations

import math

ROAD_FACTOR = 1.25  # straight line -> road km


def haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def road_km(a, b) -> float:
    """a, b: objects/dicts with lat/lng."""
    get = (lambda o, k: o[k]) if isinstance(a, dict) else (lambda o, k: getattr(o, k))
    return round(haversine_km(get(a, "lat"), get(a, "lng"), get(b, "lat"), get(b, "lng")) * ROAD_FACTOR, 1)
