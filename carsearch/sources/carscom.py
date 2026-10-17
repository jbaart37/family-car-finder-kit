"""Cars.com: each result card carries a data-vehicle-details JSON attribute."""
import html
import json
import re

from ..http import TIMEOUT, pause
from ..models import Listing, to_int

NAME = "Cars.com"
BODY = {"suv": "suv", "sedan": "sedan", "truck": "pickup_truck", "coupe": "coupe", "convertible": "convertible",
        "hatchback": "hatchback", "minivan": "minivan", "van": "cargo_van", "wagon": "wagon"}
RADII = [10, 20, 30, 40, 50, 75, 100, 150, 200, 250, 500]
CARD = re.compile(r'data-vehicle-details="([^"]*)"')
MAX_PAGES = 20


def search(p, session):
    radius = next((r for r in RADII if r >= p.radius), "all")
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        q = {"stock_type": "used", "zip": p.zip, "maximum_distance": radius,
             "body_style_slugs[]": BODY[p.body], "page_size": 100, "page": page, "sort": "best_match_desc"}
        if p.max_price:
            q["list_price_max"] = p.max_price
        if p.max_miles:
            q["mileage_max"] = p.max_miles
        if p.min_year:
            q["year_min"] = p.min_year
        r = session.get("https://www.cars.com/shopping/results/", params=q, timeout=TIMEOUT)
        r.raise_for_status()
        rows = [json.loads(html.unescape(m)) for m in CARD.findall(r.text)]
        fresh = [x for x in rows if x.get("listingId") and x["listingId"] not in seen]
        for x in fresh:
            seen.add(x["listingId"])
            out.append(_listing(x))
        if not fresh or len(out) >= p.max_per_source:
            break
        pause()
    return out[: p.max_per_source]


def _listing(x):
    seller = x.get("seller") or {}
    return Listing(
        source=NAME,
        url=f"https://www.cars.com/vehicledetail/{x['listingId']}/",
        title=f"{x.get('year', '')} {x.get('make', '')} {x.get('model', '')} {x.get('trim') or ''}".strip(),
        year=to_int(x.get("year")),
        make=x.get("make", ""),
        model=x.get("model", ""),
        trim=x.get("trim") or "",
        body=x.get("bodyStyle", ""),
        price=to_int(x.get("price")),
        mileage=to_int(x.get("mileage")),
        vin=(x.get("vin") or "").upper(),
        image=x.get("primaryThumbnail") or "",
        dealer=seller.get("dealerName", ""),
        dealer_zip=seller.get("zip", ""),
        seller_type="DEALER" if seller.get("dealerName") else "PRIVATE",
        certified=bool(x.get("cpoIndicator")),
    )
