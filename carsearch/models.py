import re
from dataclasses import dataclass, field

BODY_STYLES = {
    "suv": "SUV / Crossover",
    "sedan": "Sedan",
    "truck": "Pickup Truck",
    "coupe": "Coupe",
    "convertible": "Convertible",
    "hatchback": "Hatchback",
    "minivan": "Minivan",
    "van": "Van",
    "wagon": "Wagon",
}


@dataclass
class SearchParams:
    zip: str
    radius: int = 50
    body: str = "suv"
    max_price: int | None = None
    max_miles: int | None = None
    min_year: int | None = None
    keywords: list[str] = field(default_factory=list)  # e.g. ["Toyota RAV4", "Honda"]
    sources: list[str] = field(default_factory=lambda: ["cargurus", "autotrader", "carscom", "carvana"])
    max_per_source: int = 300
    min_tier: int = 2
    max_local: int = 40  # how many top local picks to flag (0 = no cap)
    max_online: int = 15
    max_per_model: int = 4  # within the top picks, so one model can't crowd out the rest
    sizes: list[str] = field(default_factory=list)  # SUV size classes to keep, e.g. ["compact", "midsize"]; empty = all


@dataclass
class Listing:
    source: str
    url: str
    title: str
    year: int | None = None
    make: str = ""
    model: str = ""
    trim: str = ""
    body: str = ""
    price: float | None = None
    mileage: int | None = None
    vin: str = ""
    image: str = ""
    dealer: str = ""
    city: str = ""
    state: str = ""
    dealer_zip: str = ""
    distance: float | None = None
    seller_type: str = "DEALER"  # DEALER | PRIVATE | RETAILER
    franchise: bool | None = None
    certified: bool = False
    deal_rating: str = ""
    days_on_market: int | None = None
    market_value: int | None = None
    market_src: str = ""
    price_diff: int | None = None  # price - market_value; negative = below market
    channel: str = "local"  # local = dealer lot you can visit; online = delivered (Carvana etc.)
    group: str = ""
    score: float | None = None
    top: bool = False
    size: str = ""  # SUV size class: subcompact | compact | midsize | fullsize | "" (unknown)
    tier: int = 0
    tier_label: str = ""
    dealer_count: int = 0
    also_on: list = field(default_factory=list)


def to_int(v):
    """'46,900' / '46900.0' / 46900 -> 46900; anything unparseable -> None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    digits = re.sub(r"[^\d.]", "", str(v))
    try:
        return int(float(digits)) if digits else None
    except ValueError:
        return None
