"""Car Finder: search large used-car sites near you and review results in a local web page.

  python car_agent.py serve                  # interactive page at http://localhost:8765
  python car_agent.py serve --share          # also reachable by family on your home Wi-Fi
  python car_agent.py search --open          # run the family filters once, save an HTML report
  python car_agent.py search --body sedan --max-price 25000 --max-miles 50000 --open
"""
import argparse
import json
import socket
import sys
import threading
import webbrowser
from datetime import datetime

from carsearch.engine import ROOT, RESULTS, list_saved, load_config, load_saved, run_search
from carsearch.models import BODY_STYLES, SearchParams
from carsearch.reputation import TIERS
from carsearch.sizes import size_of
from carsearch.sources import SOURCES

WEB = ROOT / "web"
REPORTS = ROOT / "reports"
VOTES = RESULTS / "votes.json"
VOTE_VALUES = ("love", "like", "hate")
PROFILE_KEYS = ("zip", "radius", "body", "max_price", "max_miles", "min_year", "keywords", "sources", "sizes",
                "min_tier", "max_local", "max_online", "max_per_model")
_lock = threading.Lock()


def family_profile(cfg):
    d = {"zip": cfg.get("default_zip", ""), "radius": cfg.get("default_radius", 50),
         "body": cfg.get("default_body", "suv"), "max_price": None, "max_miles": None, "min_year": None,
         "keywords": [], "sources": list(SOURCES), "min_tier": cfg.get("min_tier", 2),
         "max_local": 40, "max_online": 15, "max_per_model": 4, "sizes": []}
    d.update(cfg.get("family_profile") or {})
    return d


def params_from(d, cfg):
    def num(k, default=None):
        v = d.get(k)
        return int(v) if v not in (None, "") else default
    kw = d.get("keywords") or []
    if isinstance(kw, str):
        kw = [k.strip() for k in kw.split(",") if k.strip()]
    return SearchParams(
        zip=str(d.get("zip", "")).strip()[:5],
        radius=num("radius", 50),
        body=d.get("body") or "suv",
        max_price=num("max_price"),
        max_miles=num("max_miles"),
        min_year=num("min_year"),
        keywords=kw,
        sources=d.get("sources") or list(SOURCES),
        max_per_source=num("max_per_source", cfg.get("max_per_source", 300)),
        min_tier=num("min_tier", cfg.get("min_tier", 2)),
        max_local=num("max_local", 40),
        max_online=num("max_online", 15),
        max_per_model=num("max_per_model", 4),
        sizes=[x.strip() for x in (d.get("sizes") if isinstance(d.get("sizes"), list) else str(d.get("sizes") or "").split(",")) if x.strip()],
    )


def save_profile(d):
    """Write the family filters back into config.json (keeps every other setting)."""
    with _lock:
        cfg = load_config()
        p = params_from(d, cfg)
        cfg["family_profile"] = {k: getattr(p, k) for k in PROFILE_KEYS}
        (ROOT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg["family_profile"]


def family_members(cfg):
    """Names from setup: config "family" is a list of {"name", "theme"} (a plain "family_members" list also works)."""
    people = cfg.get("family") or [{"name": n} for n in cfg.get("family_members", [])]
    return [p["name"] for p in people if p.get("name")] or ["Me"]


def family_themes(cfg):
    return {p["name"]: p.get("theme", "classic") for p in cfg.get("family") or [] if p.get("name")}


def read_votes():
    return json.loads(VOTES.read_text(encoding="utf-8")) if VOTES.exists() else {}


def set_vote(listing, who, vote, manual=None):
    """Family votes: {url: {"listing": {...}, "votes": {name: love|like|hate}, "added": iso, "added_by": name, "manual": bool, "note": str}}.
    An entry stays while anyone has voted on it or someone added it by hand."""
    url = listing.get("url")
    with _lock:
        data = read_votes()
        entry = data.get(url) or {"listing": listing, "votes": {}, "added": datetime.now().isoformat(timespec="seconds")}
        if manual:
            entry.update(listing=listing, manual=True, added_by=who, note=manual.get("note", ""))
        if vote in VOTE_VALUES:
            entry["votes"][who] = vote
        else:
            entry["votes"].pop(who, None)
        if entry["votes"] or entry.get("manual"):
            data[url] = entry
        else:
            data.pop(url, None)
        RESULTS.mkdir(exist_ok=True)
        VOTES.write_text(json.dumps(data, indent=1), encoding="utf-8")
        return data


def remove_entry(url):
    with _lock:
        data = read_votes()
        data.pop(url, None)
        VOTES.write_text(json.dumps(data, indent=1), encoding="utf-8")
        return data


def write_report(result):
    """Self-contained HTML snapshot: the same page with the results (and current shortlist) baked in."""
    REPORTS.mkdir(exist_ok=True)
    page = (WEB / "index.html").read_text(encoding="utf-8")
    data = json.dumps({**result, "votes": read_votes(), "family": family_members(load_config()), "family_themes": family_themes(load_config())}).replace("</", "<\\/")
    page = page.replace("<!--PRELOAD-->", f"<script>window.__PRELOAD__ = {data};</script>")
    name = (result.get("saved_as") or f"{datetime.now():%Y%m%d-%H%M%S}.json").replace(".json", ".html")
    path = REPORTS / name
    path.write_text(page, encoding="utf-8")
    return path


def _lookup_quietly(url):
    """Best-effort details for a link; an empty dict if the site can't be read."""
    from carsearch.lookup import lookup
    try:
        fam = family_profile(load_config())
        return {k: v for k, v in lookup(url, fam.get("zip", ""), fam.get("radius", 50)).items() if v not in (None, "")}
    except Exception:
        return {}


def _int(v):
    try:
        return int(float(str(v).replace(",", "").replace("$", ""))) if v not in (None, "") else None
    except ValueError:
        raise ValueError(f"'{v}' isn't a number")


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the outbound interface
            return s.getsockname()[0]
    except OSError:
        return None


def serve(port, open_browser, share):
    from flask import Flask, jsonify, request, send_from_directory

    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/api/meta")
    def meta():
        cfg = load_config()
        return jsonify(bodies=BODY_STYLES, sources={k: m.NAME for k, m in SOURCES.items()},
                       tiers=TIERS, defaults=family_profile(cfg), family=family_members(cfg),
                       family_themes=family_themes(cfg))

    @app.post("/api/search")
    def search():
        cfg = load_config()
        try:
            return jsonify(run_search(params_from(request.get_json(force=True), cfg), cfg))
        except ValueError as e:
            return jsonify(error=str(e)), 400

    @app.post("/api/profile")
    def profile():
        try:
            return jsonify(save_profile(request.get_json(force=True)))
        except ValueError as e:
            return jsonify(error=str(e)), 400

    @app.get("/api/saved")
    def saved():
        return jsonify(list_saved())

    @app.get("/api/saved/<name>")
    def saved_one(name):
        try:
            return jsonify(load_saved(name))
        except FileNotFoundError:
            return jsonify(error="not found"), 404

    def _who(d):
        who = (d.get("who") or "").strip()
        if who not in family_members(load_config()):
            raise ValueError("pick who you are first")
        return who

    @app.get("/api/votes")
    def votes():
        return jsonify(read_votes())

    @app.post("/api/vote")
    def vote():
        d = request.get_json(force=True)
        try:
            if not (d.get("listing") or {}).get("url"):
                raise ValueError("listing.url is required")
            return jsonify(set_vote(d["listing"], _who(d), d.get("vote")))
        except ValueError as e:
            return jsonify(error=str(e)), 400

    @app.post("/api/manual")
    def manual():
        """A car someone found on their own: added straight to the family list. Missing details are fetched from the link."""
        d = request.get_json(force=True)
        try:
            who = _who(d)
            l = {k: v for k, v in (d.get("listing") or {}).items() if v not in (None, "")}
            if not str(l.get("url", "")).startswith(("http://", "https://")):
                raise ValueError("a link starting with https:// is required")
            if not (l.get("make") or l.get("model")) or not l.get("price"):
                l = {**_lookup_quietly(l["url"]), **l}   # what they typed wins over what the page says
            host = l["url"].split("/")[2].removeprefix("www.")
            listing = {
                "url": l["url"], "source": str(l.get("source") or host)[:40],
                "title": str(l.get("title") or f"Car from {host}")[:120], "year": _int(l.get("year")),
                "make": str(l.get("make") or "")[:30], "model": str(l.get("model") or "")[:40],
                "trim": str(l.get("trim") or "")[:60], "mileage": _int(l.get("mileage")), "price": _int(l.get("price")),
                "dealer": str(l.get("dealer") or "")[:80], "city": str(l.get("city") or "")[:40],
                "distance": _float(l.get("distance")), "image": str(l.get("image") or "")[:500],
                "vin": str(l.get("vin") or "")[:17], "channel": "online" if l.get("channel") == "online" else "local",
                "market_value": _int(l.get("market_value")), "market_src": str(l.get("market_src") or "")[:80],
                "size": size_of(str(l.get("model") or "")), "also_on": [], "group": "", "tier_label": "",
            }
            listing["price_diff"] = (listing["price"] - listing["market_value"]
                                     if listing["price"] and listing["market_value"] else None)
            return jsonify(set_vote(listing, who, d.get("vote"), manual={"note": str(d.get("note") or "")[:300]}))
        except ValueError as e:
            return jsonify(error=str(e)), 400

    @app.post("/api/remove")
    def remove():
        d = request.get_json(force=True)
        try:
            _who(d)
            return jsonify(remove_entry(d.get("url", "")))
        except ValueError as e:
            return jsonify(error=str(e)), 400

    @app.get("/api/lookup")
    def lookup_url():
        from carsearch.lookup import lookup
        try:
            fam = family_profile(load_config())
            return jsonify(lookup(request.args.get("url", "").strip(), fam.get("zip", ""), fam.get("radius", 50)))
        except ValueError as e:
            return jsonify(error=str(e)), 400
        except PermissionError as e:   # the site blocks automated reads
            return jsonify(error=str(e)), 502
        except Exception as e:  # site blocked us, timed out, etc. The form still works by hand.
            status = getattr(getattr(e, "response", None), "status_code", None)
            return jsonify(error=f"couldn't read that page ({f'HTTP {status}' if status else type(e).__name__}); fill in the details by hand"), 502

    host = "0.0.0.0" if share else "127.0.0.1"
    url = f"http://localhost:{port}"
    print(f"Car Finder running at {url}  (Ctrl+C to stop)")
    if share:
        ip = lan_ip()
        base = f"http://{ip or '<this-PC-ip>'}:{port}"
        print(f"Family link (same Wi-Fi): {base}   <- everyone uses this one link and picks their name")
        print("(If Windows Firewall asks, allow Python on Private networks.)")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, threaded=True)


def print_table(result, n=15):
    c = result["counts"]
    print(f"\n{result['body_label']}: {c['local']} local + {c['online']} online matches in {result['elapsed']}s "
          f"-> top {c['top_local']} local / {c['top_online']} online picks")
    for s in result["sources"].values():
        print(f"  {s['name']:<11} {s['count']:>4}  {s['error'] or ''}")
    for channel, heading in (("local", "GO SEE & DRIVE (local dealers)"), ("online", "ONLINE / DELIVERED")):
        rows = [l for l in result["listings"] if l["top"] and l["channel"] == channel][:n]
        print(f"\n{heading}")
        for l in rows:
            diff = l["price_diff"]
            vs = f"{abs(diff):,} {'below' if diff < 0 else 'above'}" if diff is not None else "n/a"
            where = f"{l['distance']:.0f} mi" if l["distance"] is not None else "ships"
            miles = f"{l['mileage']:,}" if l["mileage"] is not None else "?"
            print(f"  {l['year']} {l['make']} {l['model'][:16]:<16} {miles:>7} mi  ${l['price']:>7,}  {vs:>13}  "
                  f"{where:>6}  {l['dealer'][:26]:<26}  {l['url']}")


def main():
    cfg = load_config()
    fam = family_profile(cfg)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the interactive local web page")
    s.add_argument("--port", type=int, default=cfg.get("port", 8765))
    s.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    s.add_argument("--share", action="store_true", help="listen on your home network so family can open it")

    q = sub.add_parser("search", help="run one search (family filters unless overridden), save an HTML report")
    q.add_argument("--zip", default=fam["zip"])
    q.add_argument("--radius", type=int, default=fam["radius"])
    q.add_argument("--body", choices=list(BODY_STYLES), default=fam["body"])
    q.add_argument("--max-price", type=int, default=fam["max_price"])
    q.add_argument("--max-miles", type=int, default=fam["max_miles"])
    q.add_argument("--min-year", type=int, default=fam["min_year"])
    q.add_argument("--make", action="append", default=None, metavar="TEXT",
                   help='make/model filter, repeatable: --make "Toyota RAV4" --make Honda')
    q.add_argument("--sources", default=",".join(fam["sources"]), help=f"comma list of {','.join(SOURCES)}")
    q.add_argument("--min-tier", type=int, default=fam["min_tier"],
                   help="; ".join(f"{k}={v}" for k, v in sorted(TIERS.items())))
    q.add_argument("--max-local", type=int, default=fam["max_local"], help="top local picks to flag (0 = all)")
    q.add_argument("--max-online", type=int, default=fam["max_online"], help="top online picks to flag (0 = all)")
    q.add_argument("--sizes", default=",".join(fam["sizes"]),
                   help="SUV sizes to keep, comma list of subcompact,compact,midsize,fullsize (empty = all)")
    q.add_argument("--max-per-source", type=int, default=cfg.get("max_per_source", 300))
    q.add_argument("--open", action="store_true", help="open the HTML report in your browser")
    q.add_argument("--json", action="store_true", help="print the full result JSON instead of a table")

    a = ap.parse_args()
    if a.cmd == "serve":
        serve(a.port, not a.no_open, a.share)
        return

    p = params_from({"zip": a.zip, "radius": a.radius, "body": a.body, "max_price": a.max_price,
                     "max_miles": a.max_miles, "min_year": a.min_year,
                     "keywords": a.make if a.make is not None else fam["keywords"],
                     "sources": [x.strip() for x in a.sources.split(",") if x.strip()],
                     "min_tier": a.min_tier, "max_local": a.max_local, "max_online": a.max_online,
                     "max_per_model": fam["max_per_model"], "sizes": a.sizes, "max_per_source": a.max_per_source}, cfg)
    try:
        result = run_search(p, cfg)
    except ValueError as e:
        sys.exit(f"error: {e}")
    report = write_report(result)
    if a.json:
        print(json.dumps(result, indent=1))
    else:
        print_table(result)
    print(f"\nReport: {report}")
    if a.open:
        webbrowser.open(report.as_uri())


if __name__ == "__main__":
    main()
