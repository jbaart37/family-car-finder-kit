"""Offline ZIP-to-ZIP distance (pgeocode downloads the GeoNames US table once and caches it)."""
import math
from functools import lru_cache

_geo = None


@lru_cache(maxsize=4096)
def miles_between(zip_a, zip_b):
    global _geo
    if not zip_a or not zip_b:
        return None
    if _geo is None:
        import pgeocode
        _geo = pgeocode.GeoDistance("us")
    km = _geo.query_postal_code(zip_a[:5], zip_b[:5])
    if km is None or (isinstance(km, float) and math.isnan(km)):
        return None
    return round(float(km) * 0.621371, 1)
