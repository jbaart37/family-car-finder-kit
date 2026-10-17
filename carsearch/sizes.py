"""SUV size classes. The listing sites lump every SUV/crossover into one body style, so size is looked up by model.
Models not listed come back "" and are never filtered out (better to show an unknown than hide a good car)."""
import re

SIZES = {
    "subcompact": [
        "trax", "trailblazer", "encore", "encore gx", "envista", "kona", "venue", "hr-v", "kicks", "rogue sport",
        "seltos", "soul", "niro", "ecosport", "renegade", "crosstrek", "cx-3", "cx-30", "mx-30", "taos", "c-hr",
        "500x", "outlander sport", "countryman", "qx30", "ux", "x1", "x2", "gla", "q3", "xc40", "range rover evoque",
        "hr v", "cx30",
    ],
    "compact": [
        "rav4", "cr-v", "escape", "rogue", "equinox", "tucson", "sportage", "cx-5", "cx-50", "forester", "tiguan",
        "compass", "patriot", "cherokee", "terrain", "envision", "eclipse cross", "outlander", "bronco sport", "corolla cross",
        "rdx", "nx", "q5", "x3", "x4", "glc", "xc60", "macan", "qx50", "xt4", "xt5", "mkc", "corsair", "ioniq 5",
        "ev6", "mustang mach-e", "model y", "ariya", "bz4x", "solterra", "id.4", "range rover velar", "discovery sport",
        "cr v", "cx5", "rav 4",
    ],
    "midsize": [
        "explorer", "edge", "highlander", "grand highlander", "4runner", "venza", "pilot", "passport", "santa fe",
        "palisade", "sorento", "telluride", "murano", "pathfinder", "grand cherokee", "durango", "traverse", "blazer",
        "acadia", "enclave", "atlas", "atlas cross sport", "ascent", "cx-9", "cx-90", "cx-70", "xt6", "mdx", "rx", "gx",
        "q7", "q8", "x5", "x6", "gle", "xc90", "nautilus", "aviator", "mkx", "mkt", "bronco", "wrangler", "model x",
        "equinox ev", "blazer ev", "flex", "range rover sport", "discovery", "land cruiser",
    ],
    "fullsize": [
        "tahoe", "suburban", "yukon", "yukon xl", "expedition", "expedition max", "sequoia", "armada", "escalade",
        "escalade esv", "navigator", "wagoneer", "grand wagoneer", "qx80", "qx56", "lx", "gls", "x7", "range rover",
        "excursion",
    ],
}
LABELS = {"subcompact": "Subcompact", "compact": "Compact", "midsize": "Midsize", "fullsize": "Full-size"}

# longest names first, so "rogue sport" beats "rogue" and "grand cherokee" beats "cherokee"
_KEYS = sorted(((name, size) for size, names in SIZES.items() for name in names), key=lambda x: -len(x[0]))


def size_of(model):
    m = re.sub(r"\s+", " ", (model or "").lower()).strip()
    for name, size in _KEYS:
        if m == name or m.startswith(name + " ") or m.startswith(name + "-"):
            return size
    return ""
