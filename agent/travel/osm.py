"""OpenStreetMap place lookup through the public Nominatim server.

GET https://nominatim.openstreetmap.org/search finds a named place in a city and returns where it is, what kind of
place it is, and (with extratags) its opening hours when OpenStreetMap has them. Free, but the public server has a
usage policy (https://operations.osmfoundation.org/policies/nominatim/): at most 1 request a second for the whole
app, a User-Agent that names the app, and results cached. Data © OpenStreetMap contributors (ODbL); show that credit
wherever results appear.
"""

import math
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import requests

URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TechTreks-tripbot/0.1 (+https://github.com/NeilB18/TechTreks-Project)"
ATTRIBUTION = "© OpenStreetMap contributors"
MIN_INTERVAL_S = 1.0
CACHE_SIZE = 2000

_lock = threading.Lock()
_last_request = 0.0
_cache: dict[tuple[str, str], "Place | None"] = {}
_area_cache: dict[tuple, list[dict]] = {}


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    kind: str  # OpenStreetMap category/type, e.g. "amenity/restaurant", "tourism/museum"
    address: str
    opening_hours: str | None = None  # the raw OpenStreetMap tag, e.g. "Mo-Fr 09:00-17:00; Sa 10:00-14:00"
    hours: dict[int, list[tuple[int, int]]] | None = field(default=None)  # parsed; None = unknown
    osm_url: str = ""
    maps_url: str = ""


def maps_url(name: str, city: str) -> str:
    """A Google Maps search link (a plain URL: no API key, no cost)."""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(f'{name}, {city}')}"


def short_address(place: Place) -> str:
    """The street and neighborhood from the full OpenStreetMap address, e.g. "3555 Southwest 8th Street, Little
    Havana" (the place's own name comes off the front, and a house number joins its street)."""
    parts = [p.strip() for p in place.address.split(",")]
    if parts and parts[0].lower() == place.name.lower():
        parts = parts[1:]
    if len(parts) > 1 and parts[0].isdigit():
        parts = [f"{parts[0]} {parts[1]}"] + parts[2:]
    return ", ".join(parts[:2]) or place.name


def lookup(name: str, city: str, timeout: float = 10) -> Place | None:
    """The best OpenStreetMap match for `name` in `city`, or None if there isn't one. Answers (including "not found")
    are cached, so the same place is looked up once. Raises on HTTP or network problems (callers decide what to do)."""
    key = (name.strip().lower(), city.strip().lower())
    if key in _cache:
        return _cache[key]
    _wait_turn()
    resp = requests.get(URL, timeout=timeout, headers={"User-Agent": USER_AGENT}, params={
        "q": f"{name}, {city}" if city.strip() else name, "format": "jsonv2", "limit": 1, "extratags": 1})
    resp.raise_for_status()
    results = resp.json()
    place = _place(results[0], name, city) if results else None
    if len(_cache) >= CACHE_SIZE:
        _cache.pop(next(iter(_cache)))  # oldest first
    _cache[key] = place
    return place


def search_area(phrase: str, lat: float, lon: float, radius_m: int, timeout: float = 10) -> list[dict]:
    """Up to 40 places Nominatim finds for a category phrase ("cafe", "restaurant", "pharmacy") inside a box around a
    point: [{name, lat, lon, opening_hours, cuisine, street, website}]. Nominatim ranks them by prominence, not
    distance, so a busy area can leave out a close one. Cached and spaced out like `lookup`; raises on HTTP or network
    problems."""
    key = (phrase, round(lat, 3), round(lon, 3), radius_m)
    if key in _area_cache:
        return _area_cache[key]
    dlat = radius_m / 111320
    dlon = radius_m / (111320 * math.cos(math.radians(lat)))
    _wait_turn()
    resp = requests.get(URL, timeout=timeout, headers={"User-Agent": USER_AGENT}, params={
        "q": phrase, "format": "jsonv2", "limit": 40, "bounded": 1, "extratags": 1, "addressdetails": 1,
        "viewbox": f"{lon - dlon:.6f},{lat + dlat:.6f},{lon + dlon:.6f},{lat - dlat:.6f}"})
    resp.raise_for_status()
    places = []
    for r in resp.json():
        tags, addr = r.get("extratags") or {}, r.get("address") or {}
        if not r.get("name"):
            continue
        street = " ".join(p for p in (addr.get("house_number"), addr.get("road")) if p) or None
        places.append({"name": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"]),
                       "opening_hours": tags.get("opening_hours"), "cuisine": tags.get("cuisine"),
                       "street": street, "website": tags.get("website")})
    if len(_area_cache) >= CACHE_SIZE:
        _area_cache.pop(next(iter(_area_cache)))
    _area_cache[key] = places
    return places


def _wait_turn() -> None:
    """Space requests at least MIN_INTERVAL_S apart across all threads (the public server's limit)."""
    global _last_request
    with _lock:
        wait = _last_request + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


def _place(r: dict, name: str, city: str) -> Place:
    hours_tag = (r.get("extratags") or {}).get("opening_hours")
    return Place(
        name=r.get("name") or name,
        lat=float(r["lat"]),
        lon=float(r["lon"]),
        kind=f"{r.get('category', '')}/{r.get('type', '')}",
        address=r.get("display_name", ""),
        opening_hours=hours_tag,
        hours=parse_opening_hours(hours_tag) if hours_tag else None,
        osm_url=f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}" if r.get("osm_type") else "",
        maps_url=maps_url(r.get("name") or name, city),
    )


# ------------------------------------------------------------------ opening hours
DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_RULE = re.compile(r"^(?:(?P<days>[A-Z][a-z](?:\s*[-,]\s*[A-Z][a-z])*)\s+)?(?P<times>.+)$")
_RANGE = re.compile(r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\+?$")


def parse_opening_hours(text: str) -> dict[int, list[tuple[int, int]]] | None:
    """The common OpenStreetMap opening_hours formats, as {weekday 0-6 (Monday=0): [(open, close) in minutes]}.
    A close time past midnight is over 1440 (e.g. 18:00-02:00 is (1080, 1560)). Days not listed are closed.
    Returns None for anything it doesn't understand (public holidays, months, week numbers, comments...), so callers
    say "hours unknown" rather than guess."""
    text = text.strip()
    if text == "24/7":
        return {d: [(0, 1440)] for d in range(7)}
    week: dict[int, list[tuple[int, int]]] = {}
    for rule in filter(None, (r.strip() for r in text.split(";"))):
        if rule.startswith(("PH", "SH")):
            continue  # public/school holiday rules: a trip day is rarely one, so they don't block the rest
        m = _RULE.match(rule)
        if not m:
            return None
        days = _days(m["days"]) if m["days"] else list(range(7))
        times = m["times"].strip()
        if days is None:
            return None
        if times in ("off", "closed"):
            for d in days:
                week.pop(d, None)
            continue
        ranges = []
        for part in times.split(","):
            r = _RANGE.match(part.strip())
            if not r:
                return None
            start = int(r[1]) * 60 + int(r[2])
            end = int(r[3]) * 60 + int(r[4])
            if end <= start:
                end += 1440  # closes after midnight
            ranges.append((start, end))
        for d in days:  # a later rule for the same day replaces an earlier one, as in the spec
            week[d] = list(ranges)
    return week


def _days(spec: str) -> list[int] | None:
    out: list[int] = []
    for part in (p.strip() for p in spec.split(",")):
        if "-" in part:
            a, b = (s.strip() for s in part.split("-"))
            if a not in DAYS or b not in DAYS:
                return None
            i, j = DAYS.index(a), DAYS.index(b)
            out += [d % 7 for d in range(i, j + 1 if j >= i else j + 8)]  # "Fr-Mo" wraps past Sunday
        elif part in DAYS:
            out.append(DAYS.index(part))
        else:
            return None
    return out
