"""Autotrader: parses the schema.org CollectionPage JSON embedded in the results page (100 per page)."""
import json
import re

from ..http import TIMEOUT, new_session, pause
from ..models import Listing, to_int

NAME = "Autotrader"
PAGE = 100
BODY = {"suv": "suv-crossover", "sedan": "sedan", "truck": "truck", "coupe": "coupe",
        "convertible": "convertible", "hatchback": "hatchback", "minivan": "van-minivan",
        "van": "van-minivan", "wagon": "wagon"}
RADII = [10, 25, 50, 75, 100, 200, 300, 500]
SCHEMA = re.compile(r'data-cmp="listingsCollectionSchema" type="application/ld\+json">(.*?)</script>', re.S)


def search(p, session):
    radius = next((r for r in RADII if r >= p.radius), 0)  # 0 = any distance
    out, seen, first = [], set(), 0
    while len(out) < p.max_per_source:
        q = {"zip": p.zip, "searchRadius": radius, "numRecords": PAGE, "firstRecord": first}
        if p.max_price:
            q["maxPrice"] = p.max_price
        if p.max_miles:
            q["mileage"] = p.max_miles
        if p.min_year:
            q["startYear"] = p.min_year
        r, m = _fetch(session, BODY[p.body], q)
        if not m:
            if first == 0:
                raise RuntimeError("results data not found (page layout changed or bot check)")
            break
        if BODY[p.body] not in r.url:  # unknown body slugs silently redirect to all body styles
            raise RuntimeError(f"body style '{BODY[p.body]}' not recognized (redirected to {r.url})")
        rows = json.loads(m.group(1)).get("about", {}).get("offers", {}).get("itemOffered", [])
        fresh = [x for x in rows if x.get("offers", {}).get("url") not in seen]
        for x in fresh:
            seen.add(x["offers"].get("url"))
            out.append(_listing(x, p.body))
        if len(rows) < PAGE or not fresh:
            break
        first += PAGE
        pause()
    return out[: p.max_per_source]


def _fetch(session, slug, q):
    """One retry with a fresh session: Autotrader occasionally serves a bot-check page instead of results."""
    for attempt in range(2):
        r = session.get(f"https://www.autotrader.com/cars-for-sale/used-cars/{slug}", params=q, timeout=TIMEOUT)
        r.raise_for_status()
        m = SCHEMA.search(r.text)
        if m or attempt:
            return r, m
        session = new_session()
        pause()


def _listing(x, body):
    offer = x.get("offers", {})
    seller = offer.get("seller", {})
    addr = seller.get("address", {})
    odo = x.get("mileageFromOdometer")
    name = x.get("name", "")
    model = x.get("model", "")
    year = re.search(r"\b(19|20)\d{2}\b", name)
    return Listing(
        source=NAME,
        url=offer.get("url", ""),
        title=re.sub(r"^(Used|Certified|New)\s+", "", name),
        year=int(year.group(0)) if year else None,
        make=(x.get("brand") or {}).get("name", ""),
        model=model,
        trim=name.split(model, 1)[1].strip() if model and model in name else "",
        body=body,
        price=to_int(offer.get("price")),
        mileage=to_int(odo.get("value") if isinstance(odo, dict) else odo),
        vin=(x.get("vehicleIdentificationNumber") or "").upper(),
        image=x["image"] if isinstance(x.get("image"), str) else "",
        dealer=seller.get("name", ""),
        city=addr.get("addressLocality", ""),
        state=addr.get("addressRegion", ""),
        dealer_zip=addr.get("postalCode", ""),
        certified=name.startswith("Certified"),
    )
