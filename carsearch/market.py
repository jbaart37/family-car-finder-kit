"""Estimated market value for each listing, so the page can show "$X below / above market".

Order of preference:
1. CarGurus' own instant market value (IMV) for that exact listing.
2. A fit over CarGurus IMVs of the same make/model within +/-1 model year, adjusted for year and mileage.
3. A fit over asking prices of similar listings in this search. This is rougher: the search's price cap trims
   expensive comps, so it can make cars near the cap look slightly over market.
"""
import statistics
from collections import defaultdict

import numpy as np

MIN_COMPS = 4


def _key(l):
    return (l.make.lower(), l.model.lower())


def _predict(comps, l):
    near = [c for c in comps if abs(c[0] - l.year) <= 1 and c[3] is not l]
    if len(near) < MIN_COMPS:
        return None, 0
    values = np.array([c[2] for c in near], float)
    median = float(np.median(values))
    years = {c[0] for c in near}
    if len(near) >= 8 and len(years) > 1:
        # centered on this car's year and mileage, so the intercept is the prediction
        X = np.column_stack([np.ones(len(near)), [c[0] - l.year for c in near],
                             [(c[1] - l.mileage) / 10000 for c in near]])
        coef, *_ = np.linalg.lstsq(X, values, rcond=None)
        value = float(coef[0])
    else:
        # small sample: median, nudged ~8 cents per mile of difference from the comps' median mileage
        value = median + (statistics.median(c[1] for c in near) - l.mileage) * 0.08
    return min(max(value, median * 0.6), median * 1.4), len(near)


def estimate(listings):
    imv, asks = defaultdict(list), defaultdict(list)
    for l in listings:
        if not (l.year and l.mileage is not None and l.price):
            continue
        if l.market_src == "CarGurus":
            imv[_key(l)].append((l.year, l.mileage, l.market_value, l))
        asks[_key(l)].append((l.year, l.mileage, l.price, l))

    for l in listings:
        if not l.market_value and l.year and l.mileage is not None:
            value, n = _predict(imv[_key(l)], l)
            src = f"Estimated from {n} CarGurus market values"
            if value is None:
                value, n = _predict(asks[_key(l)], l)
                src = f"Rough estimate from {n} similar listings"
            if value:
                l.market_value, l.market_src = int(round(value, -1)), src
        if l.market_value and l.price:
            l.price_diff = int(l.price - l.market_value)
