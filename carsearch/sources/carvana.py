"""Carvana: national online retailer (ships to you, so no local distance). Parses schema.org Vehicle JSON."""
import base64
import json
import re

from ..http import TIMEOUT, pause
from ..models import Listing, to_int

NAME = "Carvana"
# values for the bodyStyles filter in the base64 "cvnaid" query param (Carvana has no cargo vans)
BODY = {"suv": "Suv", "sedan": "Sedan", "truck": "Pickup", "coupe": "Coupe", "convertible": "Convertible",
        "hatchback": "Hatchback", "minivan": "Minivan", "wagon": "Wagon"}
LD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
MAX_PAGES = 8


def search(p, session):
    if p.body not in BODY:
        raise RuntimeError(f"Carvana doesn't sell {p.body}s")
    filters = {"bodyStyles": [BODY[p.body]]}
    if p.max_price:
        filters["price"] = {"max": p.max_price}
    if p.max_miles:
        filters["mileage"] = {"max": p.max_miles}
    q = {"cvnaid": base64.b64encode(json.dumps({"filters": filters}).encode()).decode()}
    out, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        r = session.get("https://www.carvana.com/cars", params={**q, "page": page}, timeout=TIMEOUT)
        r.raise_for_status()
        rows = []
        for block in LD.findall(r.text):
            try:
                d = json.loads(block)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("@type") == "Vehicle":
                rows.append(d)
        fresh = [x for x in rows if x.get("sku") not in seen]
        for x in fresh:
            seen.add(x.get("sku"))
            out.append(_listing(x, p.body))
        if not fresh or len(out) >= p.max_per_source:
            break
        pause()
    return out[: p.max_per_source]


def _listing(x, body):
    name = x.get("name", "")
    model = x.get("model", "")
    # description looks like: "Used 2024 Chevrolet Trax LS with 11584 miles - $21,590"
    trim = re.search(re.escape(model) + r"\s+(.*?)\s+with\s+\d", x.get("description", "")) if model else None
    return Listing(
        source=NAME,
        url=x.get("offers", {}).get("url", ""),
        title=f"{name} {trim.group(1)}" if trim else name,
        year=to_int(x.get("modelDate")),
        make=x.get("manufacturer") or x.get("brand", ""),
        model=model,
        trim=trim.group(1) if trim else "",
        body=body,
        price=to_int(x.get("offers", {}).get("price")),
        mileage=to_int(x.get("mileageFromOdometer")),
        vin=(x.get("vehicleIdentificationNumber") or "").upper(),
        image=x.get("image", ""),
        dealer="Carvana",
        seller_type="RETAILER",
    )
