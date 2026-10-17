"""Runs all sources in parallel, then normalizes, filters, de-duplicates and ranks."""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from collections import Counter

from . import market, reputation
from .geo import miles_between
from .http import new_session
from .models import BODY_STYLES, SearchParams
from .sizes import size_of
from .sources import SOURCES

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def load_config():
    path = ROOT / "config.json"
    if not path.exists():
        raise SystemExit("No config.json yet. Run setup first: setup.bat on Windows, ./setup.sh on Mac/Linux.")
    return json.loads(path.read_text(encoding="utf-8"))


def _run_source(key, params):
    mod = SOURCES[key]
    t0 = time.time()
    try:
        rows = mod.search(params, new_session())
        return key, rows, {"name": mod.NAME, "count": len(rows), "error": None, "seconds": round(time.time() - t0, 1)}
    except Exception as e:  # one blocked site shouldn't sink the whole search
        status = getattr(getattr(e, "response", None), "status_code", None)
        msg = f"HTTP {status} (site blocked the request)" if status else str(e)[:200]
        return key, [], {"name": mod.NAME, "count": 0, "error": msg, "seconds": round(time.time() - t0, 1)}


CAB = re.compile(r"\s+((?:Crew|Double|Quad|Regular|Extended|Access|King|Mega|Super ?Crew|Super)\s*Cab|CrewMax|XtraCab|SuperCrew)\b.*$", re.I)


def _normalize_model(model, trim):
    """Make the same model group together across sites: 'Silverado 1500 Crew Cab' -> 'Silverado 1500', 'F150' -> 'F-150'."""
    m = CAB.search(model or "")
    if m:
        trim = f"{m.group(0).strip()} {trim}".strip()
        model = model[: m.start()]
    model = re.sub(r"^([FE])(\d{3})\b", r"\1-\2", model.strip())
    return model, trim


def _matches_keywords(l, keywords):
    if not keywords:
        return True
    hay = f"{l.year} {l.make} {l.model} {l.trim} {l.title}".lower()
    return any(all(w in hay for w in kw.lower().split()) for kw in keywords if kw.strip())


def _passes(l, p):
    if p.max_price and l.price and l.price > p.max_price:
        return False
    if p.max_miles and l.mileage is not None and l.mileage > p.max_miles:
        return False
    if p.min_year and l.year and l.year < p.min_year:
        return False
    if l.distance is not None and l.distance > p.radius * 1.1:
        return False
    if p.sizes and l.size and l.size not in p.sizes:  # unknown sizes are kept
        return False
    if not l.price:  # "call for price" listings aren't comparable
        return False
    return _matches_keywords(l, p.keywords)


def _dedupe(listings):
    """Same VIN on several sites -> one row (lowest price wins), other sites kept as extra links."""
    by_vin, out = {}, []
    for l in sorted(listings, key=lambda x: x.price or 1e12):
        if not l.vin or len(l.vin) != 17:
            out.append(l)
            continue
        first = by_vin.get(l.vin)
        if first is None:
            by_vin[l.vin] = l
            out.append(l)
            continue
        first.also_on.append({"source": l.source, "url": l.url, "price": l.price})
        # borrow richer fields the winning source lacked
        for f in ("distance", "deal_rating", "days_on_market", "city", "state", "image", "trim",
                  "market_value", "market_src"):
            if not getattr(first, f) and getattr(l, f):
                setattr(first, f, getattr(l, f))
        if first.franchise is None and l.franchise is not None:
            first.franchise = l.franchise
    return out


def _assign_channel(listings, cfg):
    """local = a dealer lot within the radius you can visit and test-drive; online = delivered to you."""
    markers = [m.lower() for m in cfg.get("online_markers", [])]
    for l in listings:
        online = l.distance is None or any(m in l.dealer.lower() for m in markers)  # Carvana has no lot distance
        l.channel = "online" if online else "local"


def _rank(listings, p):
    """Score = % above/below market (+ small nudges for low miles and seller tier); flag the top picks."""
    for l in listings:
        pct = l.price_diff / l.market_value if l.price_diff is not None and l.market_value else 0.0
        if l.market_src.startswith("Rough"):  # asking-price comps are noisy; trust them half as much
            pct /= 2
        l.score = round(pct + (l.mileage or 0) / 1_000_000 - 0.01 * l.tier, 4)
    for channel, cap in (("local", p.max_local), ("online", p.max_online)):
        per_model, picked = Counter(), 0
        for l in sorted((x for x in listings if x.channel == channel), key=lambda x: x.score):
            if cap and picked >= cap:
                break
            key = (l.make.lower(), l.model.lower())
            if p.max_per_model and per_model[key] >= p.max_per_model:
                continue
            per_model[key] += 1
            picked += 1
            l.top = True


def run_search(p: SearchParams, cfg=None, save=True):
    cfg = cfg or load_config()
    if p.body not in BODY_STYLES:
        raise ValueError(f"body must be one of {list(BODY_STYLES)}")
    if not re.fullmatch(r"\d{5}", p.zip or ""):
        raise ValueError("zip must be a 5-digit US ZIP code")
    started = time.time()

    if p.keywords:  # make/model is filtered after fetching, so pull deeper to find enough matches
        p.max_per_source = min(p.max_per_source * 3, 900)
    keys = [k for k in p.sources if k in SOURCES]
    with ThreadPoolExecutor(max_workers=len(keys) or 1) as pool:
        results = list(pool.map(lambda k: _run_source(k, p), keys))

    raw, status = [], {}
    for key, rows, st in results:
        raw.extend(rows)
        status[key] = st

    for l in raw:
        l.body = BODY_STYLES[p.body]
        l.price = int(l.price) if l.price else None
        if l.make.isupper() and len(l.make) > 3:  # "MAZDA" -> "Mazda", keep "BMW"/"GMC"
            l.make = l.make.title()
        l.model, l.trim = _normalize_model(l.model, l.trim)
        l.size = size_of(l.model) if p.body == "suv" else ""
        if l.distance is None and l.dealer_zip:
            l.distance = miles_between(p.zip, l.dealer_zip)

    kept = _dedupe([l for l in raw if _passes(l, p)])
    reputation.assign(kept, cfg)
    _assign_channel(kept, cfg)
    market.estimate(kept)  # uses every match (all tiers) as comps
    final = [l for l in kept if l.tier >= p.min_tier]
    _rank(final, p)
    final.sort(key=lambda l: (l.channel != "local", l.score))

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "elapsed": round(time.time() - started, 1),
        "params": asdict(p),
        "body_label": BODY_STYLES[p.body],
        "sources": status,
        "counts": {"raw": len(raw), "after_filters": len(kept), "shown": len(final),
                   "local": sum(l.channel == "local" for l in final),
                   "online": sum(l.channel == "online" for l in final),
                   "top_local": sum(l.top and l.channel == "local" for l in final),
                   "top_online": sum(l.top and l.channel == "online" for l in final)},
        "listings": [asdict(l) for l in final],
    }
    if save:
        RESULTS.mkdir(exist_ok=True)
        name = f"{datetime.now():%Y%m%d-%H%M%S}_{p.body}_{p.zip}.json"
        (RESULTS / name).write_text(json.dumps(out), encoding="utf-8")
        out["saved_as"] = name
    return out


def list_saved(limit=30):
    if not RESULTS.exists():
        return []
    files = sorted(RESULTS.glob("2*_*.json"), reverse=True)[:limit]  # search results only, not shortlist.json
    return [f.name for f in files]


def load_saved(name):
    path = (RESULTS / name).resolve()
    if path.parent != RESULTS.resolve() or not path.exists():
        raise FileNotFoundError(name)
    return json.loads(path.read_text(encoding="utf-8"))
