"""CarGurus: JSON endpoint behind their search results page. Provides distance, franchise flag and deal rating."""
from ..http import TIMEOUT, pause
from ..models import Listing, to_int

NAME = "CarGurus"
URL = "https://www.cargurus.com/Cars/searchResults.action"
PAGE = 48
BODY = {"coupe": "bg0", "convertible": "bg1", "hatchback": "bg3", "minivan": "bg4", "truck": "bg5",
        "sedan": "bg6", "suv": "bg7", "van": "bg8", "wagon": "bg9"}
DEAL = {"GREAT_PRICE": "Great", "GOOD_PRICE": "Good", "FAIR_PRICE": "Fair",
        "HIGH_PRICE": "High", "OVERPRICED": "Overpriced"}


def search(p, session):
    out, seen, offset = [], set(), 0
    while len(out) < p.max_per_source:
        q = {"zip": p.zip, "distance": p.radius, "inventorySearchWidgetType": "AUTO",
             "bodyTypeGroup": BODY[p.body], "offset": offset, "maxResults": PAGE,
             "sortDir": "ASC", "sortType": "DEAL_SCORE"}
        if p.max_price:
            q["maxPrice"] = p.max_price
        if p.max_miles:
            q["maxMileage"] = p.max_miles
        if p.min_year:
            q["startYear"] = p.min_year
        r = session.get(URL, params=q, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json() or []
        fresh = [x for x in rows if x.get("id") not in seen]
        for x in fresh:
            seen.add(x.get("id"))
            out.append(_listing(x))
        if len(rows) < PAGE or not fresh:
            break
        offset += PAGE
        pause()
    return out[: p.max_per_source]


def _listing(x):
    city, _, state = (x.get("sellerCity") or "").rpartition(", ")
    return Listing(
        source=NAME,
        url=f"https://www.cargurus.com/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action?#listing={x['id']}",
        title=x.get("listingTitle", ""),
        year=x.get("carYear"),
        make=x.get("makeName", ""),
        model=x.get("modelName", ""),
        trim=x.get("trimName", ""),
        body=x.get("bodyTypeName", ""),
        price=x.get("price"),
        mileage=to_int(x.get("mileage")),
        vin=(x.get("vin") or "").upper(),
        image=(x.get("originalPictureData") or {}).get("url", ""),
        dealer=x.get("dealerName") or x.get("serviceProviderName") or "",
        city=city or x.get("sellerCity", ""),
        state=state or x.get("sellerRegion", ""),
        dealer_zip=x.get("sellerPostalCode", ""),
        distance=round(x["distance"], 1) if x.get("distance") is not None else None,
        seller_type="PRIVATE" if x.get("sellerType") == "PRIVATE" else "DEALER",
        franchise=x.get("isFranchiseDealer"),
        deal_rating=DEAL.get(x.get("dealRating"), ""),
        market_value=to_int(x.get("expectedPrice")),
        market_src="CarGurus" if x.get("expectedPrice") else "",
        days_on_market=x.get("daysOnMarket"),
    )
