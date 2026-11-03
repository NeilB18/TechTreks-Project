"""Nearby places ("pizza", "coffee", "pharmacy") around a point, from OpenStreetMap's Nominatim server.

Nominatim understands category words ("cafe", "bar", "pharmacy") but not food types, so a food word like "pizza" or
"sushi" searches nearby restaurants and fast food and keeps the ones whose cuisine tag or name matches. Each search
is capped at 40 places, ranked by prominence rather than distance, so a dense area can leave out a close one. There
are no ratings: results are the closest matches, not the best ones. Requests go through agent/travel/osm.py, so they
share its 1-a-second limit and cache. (The Overpass server can search by tag, but it was overloaded or ~40 s slow
when this was built, Nov 3, 2026.)
"""

import math
import re

from agent.travel import osm

# Words people use -> the Nominatim category phrases that find them.
PHRASES: dict[str, list[str]] = {
    "coffee": ["cafe"], "cafe": ["cafe"], "bar": ["bar", "pub"], "pub": ["pub"], "club": ["nightclub"],
    "nightclub": ["nightclub"], "restaurant": ["restaurant"], "food": ["restaurant", "fast food"],
    "fast food": ["fast food"], "ice cream": ["ice cream"], "bakery": ["bakery"], "pharmacy": ["pharmacy"],
    "drugstore": ["pharmacy"], "grocery": ["supermarket"], "supermarket": ["supermarket"],
    "convenience store": ["convenience store"], "atm": ["atm"], "bank": ["bank"], "beach": ["beach"],
    "park": ["park"], "museum": ["museum"], "hotel": ["hotel"],
}
FOOD_PHRASES = ["restaurant", "fast food"]  # where a food type ("pizza", "sushi") is looked for
_WHAT = re.compile(r"^[a-z][a-z '&-]{0,29}$")


def normalize(what: str) -> str | None:
    """The search word in a form the table uses ("Pizza " -> "pizza", "tacos" -> "taco"), or None if it isn't a short
    plain word or phrase."""
    w = re.sub(r"\s+", " ", (what or "").strip().lower())
    if not _WHAT.match(w):
        return None
    if w not in PHRASES and w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        w = w[:-1]  # cuisines and names are matched as substrings, so the singular finds both
    return w


def search(what: str, lat: float, lon: float, radius_m: int) -> list[dict]:
    """Named places matching `what` near a point (osm.search_area's shape), not sorted. A category word is one
    search per phrase; a food type searches restaurants and fast food and keeps the matching cuisine or name."""
    w = normalize(what)
    if w is None:
        raise ValueError(f"Can't search for {what!r}: use a short word like pizza, coffee or pharmacy")
    if w in PHRASES:
        phrases, match, boxes = PHRASES[w], None, [(lat, lon, radius_m)]
    else:
        # A food type is a filter on restaurants and fast food, and each search returns only the 40 most prominent
        # ones, so the box is split into 4 quarters: in a dense area one box found 1 of 4 pizza places within a mile,
        # quarters found all 4 (8 requests, about 8 s at 1 a second; cached after).
        dlat = radius_m / 2 / 111320
        dlon = radius_m / 2 / (111320 * math.cos(math.radians(lat)))
        phrases, match = FOOD_PHRASES, w
        boxes = [(lat + sy * dlat, lon + sx * dlon, radius_m // 2) for sy in (1, -1) for sx in (-1, 1)]
    seen: dict[tuple, dict] = {}
    for blat, blon, half in boxes:
        for phrase in phrases:
            for p in osm.search_area(phrase, blat, blon, half):
                seen.setdefault((p["name"].lower(), round(p["lat"], 4), round(p["lon"], 4)), p)
    places = list(seen.values())
    if match:
        places = [p for p in places if match in (p.get("cuisine") or "").lower() or match in p["name"].lower()]
    return places


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line (great-circle) distance in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def describe_distance(meters: float) -> tuple[str, str]:
    """("0.3 mi", "about a 7 min walk"). Walking assumes 3 mph and streets about 25% longer than a straight line."""
    miles = meters / 1609.344
    minutes = max(1, round(meters * 1.25 / 80))
    return (f"{miles:.1f} mi" if miles >= 0.1 else "under 0.1 mi"), f"about a {minutes} min walk"
