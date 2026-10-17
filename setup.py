"""Family Car Finder setup: asks a few questions and writes config.json.

Run it through setup.bat (Windows) or ./setup.sh (Mac/Linux): they install the dependencies first, then call this.
Running it again lets you change your answers; votes and past searches are kept.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE, CONFIG = ROOT / "config.example.json", ROOT / "config.json"

BODIES = ["suv", "sedan", "truck", "minivan", "hatchback", "wagon", "coupe", "convertible", "van"]
SIZES = ["subcompact", "compact", "midsize", "fullsize"]
THEMES = {
    "classic": "Classic: clean and simple",
    "ballpark": "Ballpark: softball, dogs and capybaras",
    "farmhouse": "Farmhouse: hearts, dogs, goats and sheep",
    "truckyard": "Truck Yard: pickups, diamond plate, hazard stripes",
    "garden": "Garden Party: flowers and butterflies",
    "sparkle": "Unicorn Sparkle: rainbows, unicorns and glitter",
    "beach": "Beach Day: dolphins, seashells and waves",
    "cafe": "Cozy Cafe: lattes, cats and pastries",
}


def ask(question, default=""):
    shown = f" [{default}]" if default not in ("", None) else ""
    answer = input(f"{question}{shown}: ").strip()
    return answer if answer else ("" if default is None else str(default))


def ask_number(question, default=None, allow_blank=True):
    while True:
        raw = ask(question, "" if default is None else default).replace(",", "").replace("$", "")
        if raw == "" and allow_blank:
            return None
        if raw.isdigit():
            return int(raw)
        print("  Please enter a whole number" + (", or leave it blank for no limit." if allow_blank else "."))


def ask_choice(question, options, default):
    keys = list(options)
    for i, k in enumerate(keys, 1):
        print(f"  {i}. {options[k] if isinstance(options, dict) else k}")
    while True:
        raw = ask(question, keys.index(default) + 1)
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return keys[int(raw) - 1]
        if raw in keys:
            return raw
        print(f"  Pick a number from 1 to {len(keys)}.")


def place_name(zip_code):
    """('Springfield, IL', '') for a ZIP, or ('', reason) if the lookup failed. Also downloads the ZIP table once."""
    try:
        from carsearch.geo import use_certifi
        use_certifi()   # python.org's Mac Python has no certificates until "Install Certificates" is run
        import pgeocode
        row = pgeocode.Nominatim("us").query_postal_code(zip_code)
        if isinstance(row.place_name, str):
            return f"{row.place_name.split(',')[0]}, {row.state_code}", ""
        return "", "that ZIP code wasn't found"
    except Exception as e:
        return "", f"{type(e).__name__}: {str(e)[:120]}"


def main():
    print("\n=== Family Car Finder setup ===\n")
    cfg = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    old = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    if old:
        print("You already have a config.json. Your answers will update it (votes and searches are kept).\n")
    prof = {**cfg["family_profile"], **old.get("family_profile", {})}

    # where
    while True:
        zip_code = ask("Your ZIP code", prof.get("zip") or "")
        if len(zip_code) == 5 and zip_code.isdigit():
            break
        print("  Please enter a 5-digit US ZIP code.")
    where, problem = place_name(zip_code)
    if where:
        print(f"  Found: {where}")
    else:
        print(f"  Couldn't look up that ZIP ({problem}).")
        print("  It will still work if the ZIP is right. If this mentions certificates or the internet, check your connection.")
    radius = ask_number("Search within how many miles? (10 / 25 / 50 / 75 / 100 / 200)", prof.get("radius", 50), allow_blank=False)

    # what
    print("\nWhat kind of vehicle?")
    body = ask_choice("Body style", {b: b.upper() if b == "suv" else b.title() for b in BODIES}, prof.get("body", "suv"))
    sizes = prof.get("sizes") or ["subcompact", "compact", "midsize"]
    if body == "suv":
        print("\nSUV sizes to include (full-size means Tahoe, Suburban, Expedition and similar).")
        raw = ask("Comma list of " + ", ".join(SIZES), ",".join(sizes))
        sizes = [x.strip().lower() for x in raw.split(",") if x.strip().lower() in SIZES] or sizes
    max_price = ask_number("\nMax price in dollars (blank = no limit)", prof.get("max_price"))
    max_miles = ask_number("Max mileage (blank = no limit)", prof.get("max_miles"))

    # who
    print("\nWho's voting? Each person gets their own name on the page and picks a look.")
    old_family = old.get("family") or []
    count = ask_number("How many people (1-6)", len(old_family) or 3, allow_blank=False)
    count = max(1, min(6, count))
    family = []
    for i in range(count):
        prev = old_family[i] if i < len(old_family) else {}
        while True:
            name = ask(f"\nPerson {i + 1} name", prev.get("name", ""))
            if name and all(name.lower() != f["name"].lower() for f in family):
                break
            print("  Please enter a name (each person needs a different one).")
        print(f"Theme for {name}:")
        theme = ask_choice("Theme", THEMES, prev.get("theme", list(THEMES)[(i + 1) % len(THEMES)]))
        family.append({"name": name[:30], "theme": theme})

    # local dealer groups
    print("\nOptional: big dealer groups near you (names that appear in several dealerships' names, e.g. 'Smith Auto').")
    print("They rank as 'major dealer group'. Leave blank to skip; you can add more to config.json later.")
    local_groups = {k: v for k, v in old.get("dealer_groups", {}).items() if k not in cfg["dealer_groups"]}
    raw = ask("Comma list", ", ".join(local_groups))
    for g in [x.strip() for x in raw.split(",") if x.strip()]:
        cfg["dealer_groups"][g] = [g.lower()]

    # write
    cfg["family"] = family
    cfg["family_profile"] = {**prof, "zip": zip_code, "radius": radius, "body": body, "sizes": sizes if body == "suv" else [],
                             "max_price": max_price, "max_miles": max_miles}
    cfg.pop("_readme", None)
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (ROOT / "results").mkdir(exist_ok=True)

    print(f"\nSaved {CONFIG.name}.")
    print(f"  Searching for: {body.upper() if body == 'suv' else body} within {radius} mi of {zip_code}"
          f"{' (' + where + ')' if where else ''}"
          f"{', under $' + format(max_price, ',') if max_price else ''}{', under ' + format(max_miles, ',') + ' mi' if max_miles else ''}")
    print("  Family: " + ", ".join(f"{f['name']} ({f['theme']})" for f in family))

    if ask("\nRun the first search now? It takes about a minute. (y/n)", "y").lower().startswith("y"):
        subprocess.call([sys.executable, str(ROOT / "car_agent.py"), "search"], cwd=ROOT)

    start = "start.bat" if sys.platform.startswith("win") else "./start.sh"
    print(f"\nAll set. To open the family page, run {start} and share the 'Family link' it prints.")
    print("Everyone needs to be on the same Wi-Fi as this computer, and the computer has to stay on while you're shopping.\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup stopped. Run it again any time.")
