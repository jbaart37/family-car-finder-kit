"""Seller tiering. Public sites don't publish dealer sales volume, so we use proxies:
national retailer > known large dealer group > new-car franchise dealer or a dealer with many
matching units in this search > independent > private seller."""
import re
from collections import Counter

TIERS = {
    4: "National retailer",
    3: "Major dealer group",
    2: "Franchise dealer",
    1: "Independent dealer",
    0: "Private seller",
}


def norm(name):
    return re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower()).strip()


def _has(name, terms):
    return any(re.search(r"\b" + re.escape(t) + r"\b", name) for t in terms)


def _groups(cfg):
    groups = cfg.get("dealer_groups", {})
    if isinstance(groups, list):  # older config format: plain list of name fragments
        groups = {g.title(): [g] for g in groups}
    return {label: [norm(t) for t in terms] for label, terms in groups.items()}


def assign(listings, cfg):
    counts = Counter(norm(l.dealer) for l in listings if l.dealer)
    national = [norm(t) for t in cfg.get("national_retailers", [])]
    groups = _groups(cfg)
    brands = [norm(t) for t in cfg.get("franchise_brands", [])]
    high_volume = cfg.get("high_volume_min_listings", 6)

    for l in listings:
        name = norm(l.dealer)
        l.dealer_count = counts.get(name, 0)
        l.group = next((label for label, terms in groups.items() if _has(name, terms)), "")
        if l.seller_type == "RETAILER" or _has(name, national):
            tier, label = 4, TIERS[4]
        elif l.group:
            tier, label = 3, TIERS[3]
        elif l.franchise or (l.franchise is None and _has(name, brands)):
            tier, label = 2, TIERS[2]
        elif l.seller_type == "PRIVATE" or not name:
            tier, label = 0, TIERS[0]
        elif l.dealer_count >= high_volume:
            tier, label = 2, "High-volume dealer"
        else:
            tier, label = 1, TIERS[1]
        l.tier, l.tier_label = tier, label
