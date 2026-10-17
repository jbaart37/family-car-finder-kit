"""Fill in a car from a pasted link, for the "add a car we found" form. Tried in order:
1. cars our own searches already found (instant, works for every site, including ones that block page reads)
2. CarGurus' per-listing JSON feed (their listing pages block automated reads, the feed doesn't)
3. schema.org JSON-LD on the page (Autotrader, Carvana and most dealer websites publish it)
4. page title / meta tags as a last resort
"""
import ipaddress
import json
import re
import socket
from urllib.parse import unquote, urlparse

from .engine import RESULTS
from .geo import miles_between
from .http import TIMEOUT, new_session
from .models import to_int

LD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
VEHICLE = {"car", "vehicle", "motorvehicle", "automobile"}
ONLINE_SELLERS = {"carvana.com": "Carvana", "vroom.com": "Vroom", "carmax.com": "CarMax", "shift.com": "Shift"}
FIELDS = ("year", "make", "model", "trim", "mileage", "price", "vin", "image", "dealer", "city", "dealer_zip", "distance",
          "market_value", "market_src", "price_diff", "size", "group", "tier_label", "channel", "source", "title")


def _public_host(host):
    """Refuse addresses on the home network or this PC: the server runs on the LAN, so this is a fetch-anything endpoint."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def _ids(url):
    """Site listing ids in a URL, so a link matches a saved listing even if the query string or fragment differ."""
    u = unquote(url)
    found = set(re.findall(r"(?:listing=|inventoryListing=|/details/)(\d{6,})", u))      # CarGurus
    found |= set(re.findall(r"/vehicledetail/([0-9a-f-]{20,})", u))                       # Cars.com
    found |= set(re.findall(r"/cars-for-sale/vehicle/(\d{6,})", u))                       # Autotrader
    found |= set(re.findall(r"carvana\.com/vehicle/(\d{5,})", u))                         # Carvana
    return found


def from_saved(url):
    """A car any of our past searches found, newest search first."""
    want_ids, want_url = _ids(url), url.rstrip("/")
    for path in sorted(RESULTS.glob("2*_*.json"), reverse=True):
        try:
            listings = json.loads(path.read_text(encoding="utf-8")).get("listings", [])
        except (OSError, ValueError):
            continue
        for l in listings:
            for link in [l.get("url", "")] + [o.get("url", "") for o in l.get("also_on") or []]:
                if link and (link.rstrip("/") == want_url or (want_ids and want_ids & _ids(link))):
                    out = {k: l.get(k) for k in FIELDS if l.get(k) not in (None, "")}
                    return {**out, "url": url, "found": True, "how": "from our saved searches"}
    return None


def _cargurus(url):
    ids = re.findall(r"(?:listing=|inventoryListing=|/details/)(\d{6,})", unquote(url))
    if not ids:
        return None
    r = new_session().get("https://www.cargurus.com/Cars/detailListingJson.action",
                          params={"inventoryListing": ids[0]}, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    l, seller = j.get("listing") or {}, j.get("seller") or {}
    addr = seller.get("address") or {}
    pics = l.get("pictures") or []
    out = {
        "found": bool(l), "how": "from CarGurus", "source": "CarGurus",
        "title": re.sub(r"\s+-\s+\$[\d,]+$", "", l.get("listingTitle", "")),
        "year": l.get("year"), "make": l.get("makeName", ""), "model": l.get("modelName", ""), "trim": l.get("trimName", ""),
        "mileage": to_int(l.get("mileage")), "price": to_int(l.get("price")), "vin": (l.get("vin") or "").upper(),
        "image": pics[0].get("url", "") if pics else "",
        "dealer": seller.get("name", ""), "city": addr.get("city", ""), "dealer_zip": addr.get("postalCode", ""),
        "market_value": to_int(l.get("expectedPrice")),
    }
    if out["market_value"]:
        out["market_src"] = "CarGurus"
    if l.get("status") and l["status"] != "OPEN":
        out["warning"] = f"CarGurus lists this car as {l['status'].lower()}; it may already be sold."
    return out


def _nodes(d):
    if isinstance(d, list):
        for x in d:
            yield from _nodes(x)
    elif isinstance(d, dict):
        yield d
        for k in ("@graph", "mainEntity", "itemOffered", "offers"):
            if k in d:
                yield from _nodes(d[k])


def _types(node):
    t = node.get("@type", [])
    return {x.lower() for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)}


def _name(v):
    return v.get("name", "") if isinstance(v, dict) else (v or "")


def _first(v):
    return v[0] if isinstance(v, list) and v else v


def _vehicle_node(html):
    for block in LD.findall(html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _nodes(data):
            types = _types(node)
            if types & VEHICLE or ("product" in types and ("vehicleIdentificationNumber" in node or "mileageFromOdometer" in node)):
                return node
    return None


def _meta(html, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']*)', html, re.I)
    return m.group(1).strip() if m else ""


def _from_page(url):
    r = new_session().get(url, timeout=TIMEOUT, allow_redirects=True)
    if r.status_code in (401, 403, 429):
        host = urlparse(url).hostname.removeprefix("www.")
        raise PermissionError(f"{host} blocks automatic reading of its listing pages; please type the details in")
    r.raise_for_status()
    html = r.text
    out = {"found": False, "how": "from the listing page"}
    node = _vehicle_node(html)
    if node:
        offer = _first(node.get("offers")) or {}
        seller = offer.get("seller") or node.get("seller") or {}
        addr = (_first(seller.get("address")) or {}) if isinstance(seller, dict) else {}
        odo = node.get("mileageFromOdometer")
        image = _first(node.get("image"))
        out.update(
            found=True,
            title=node.get("name", ""),
            year=to_int(node.get("vehicleModelDate") or node.get("modelDate") or node.get("productionDate")),
            make=_name(node.get("brand")) or _name(node.get("manufacturer")),
            model=_name(node.get("model")),
            trim=node.get("vehicleConfiguration", ""),
            mileage=to_int(odo.get("value") if isinstance(odo, dict) else odo),
            price=to_int(offer.get("price") or (offer.get("priceSpecification") or {}).get("price")),
            vin=(node.get("vehicleIdentificationNumber") or "").upper(),
            image=image.get("url", "") if isinstance(image, dict) else (image or ""),
            dealer=_name(seller),
            city=addr.get("addressLocality", "") if isinstance(addr, dict) else "",
            dealer_zip=addr.get("postalCode", "") if isinstance(addr, dict) else "",
        )
    else:
        title = _meta(html, "og:title") or (re.search(r"<title>(.*?)</title>", html, re.S | re.I) or [None, ""])[1].strip()
        price = re.search(r"\$\s?(\d{1,3}(?:,\d{3})+)", html)
        miles = re.search(r"(\d{1,3}(?:,\d{3})+)\s*(?:mi\b|miles)", html, re.I)
        out.update(title=title, image=_meta(html, "og:image"),
                   price=to_int(price.group(1)) if price else None, mileage=to_int(miles.group(1)) if miles else None)
        out["found"] = bool(out["price"] or out["mileage"])
    return out


def lookup(url, home_zip="", radius=50):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("enter a full web address starting with https://")
    host = u.hostname.removeprefix("www.")

    out = from_saved(url)
    if not out:
        if not _public_host(u.hostname):
            raise ValueError("only public websites can be looked up")
        out = (_cargurus(url) if host.endswith("cargurus.com") else None) or _from_page(url)
        out["url"] = url

    out.setdefault("source", {"cars.com": "Cars.com", "autotrader.com": "Autotrader"}.get(host, ONLINE_SELLERS.get(host, host)))
    for site, name in ONLINE_SELLERS.items():
        if host.endswith(site):
            if not out.get("dealer"):
                out["dealer"] = name
            out.setdefault("channel", "online")
    m = re.search(r"\b(19[89]\d|20[0-3]\d)\s+([A-Za-z-]+)\s+([A-Za-z0-9-]+)", out.get("title") or "")
    if m:  # "2021 Toyota RAV4 XLE" -> fill gaps
        out["year"] = out.get("year") or int(m.group(1))
        out["make"] = out.get("make") or m.group(2)
        out["model"] = out.get("model") or m.group(3)
    if out.get("distance") is None and out.get("dealer_zip") and home_zip:
        out["distance"] = miles_between(home_zip, out["dealer_zip"])
    if "channel" not in out and out.get("distance") is not None:
        out["channel"] = "local" if out["distance"] <= radius * 1.1 else "online"
    return out
