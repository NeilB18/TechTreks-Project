"""Lays the agent's suggested stops out into days.

Each day has a simple template: a morning and an afternoon slot for activities, lunch and dinner for food, and a
night slot. Activities are split across the days first, in map order (each one next to its nearest neighbor), so a
day stays in one area; one that's closed on its day moves to the closest day it's open. Food and night stops then go
to the day with the fewest stops of their kind (so meals spread out), and among those the day whose stops are
closest. Opening hours are respected when they're known: a stop that would be closed is moved to another free slot,
and if none works it's flagged so the agent can mention it.
"""

import math
from datetime import date, timedelta

# name, the kind of stop it's for, start and end in minutes after midnight
SLOTS = [("morning", "activity", 600, 720), ("lunch", "food", 750, 840), ("afternoon", "activity", 870, 1050),
         ("dinner", "food", 1140, 1260), ("night", "night", 1290, 1410)]
KINDS = ("food", "activity", "night")


def is_open(hours: dict | None, weekday: int, start: int, end: int) -> bool | None:
    """Whether a place with these parsed hours is open for the whole slot (None = hours unknown). A range that runs
    past midnight on the day before counts too."""
    if hours is None:
        return None
    today = hours.get(weekday, [])
    yesterday = [(o - 1440, c - 1440) for o, c in hours.get((weekday - 1) % 7, []) if c > 1440]
    return any(o <= start and end <= c for o, c in today + yesterday)


def plan_days(stops: list[dict], first_day: date, n_days: int) -> list[dict]:
    """stops: {"kind", "lat", "lon", "hours", ...} (lat/lon/hours may be None). Returns
    [{"date", "items": [stop + "slot", "start", "end", "hours_conflict"]}] with items in time order."""
    days = [{"date": first_day + timedelta(days=i), "items": []} for i in range(n_days)]
    activities = _map_order([s for s in stops if s["kind"] == "activity"])
    per_day = math.ceil(len(activities) / n_days) if activities else 0
    for i, s in enumerate(activities):
        day = days[min(i // per_day, n_days - 1)]
        fits = [d for d in days if _open_slots(d, s)]
        _place(day if _open_slots(day, s) or not fits else _best_day(fits, s), s)
    for s in (s for s in stops if s["kind"] != "activity"):
        _place(_best_day(days, s), s)
    for day in days:
        day["items"].sort(key=lambda it: it["start_min"])
    return days


def _map_order(stops: list[dict]) -> list[dict]:
    """Nearest-neighbor chain starting from the stop farthest from the middle; stops without coordinates go last."""
    located = [s for s in stops if s.get("lat") is not None]
    if not located:
        return stops
    mid = (sum(s["lat"] for s in located) / len(located), sum(s["lon"] for s in located) / len(located))
    chain = [max(located, key=lambda s: _dist(s, mid))]
    rest = [s for s in located if s is not chain[0]]
    while rest:
        nxt = min(rest, key=lambda s: _dist(s, (chain[-1]["lat"], chain[-1]["lon"])))
        chain.append(nxt)
        rest.remove(nxt)
    return chain + [s for s in stops if s.get("lat") is None]


def _dist(s: dict, point: tuple[float, float]) -> float:
    # Plain degrees with longitude scaled by latitude: fine for comparing places inside one city.
    return math.hypot(s["lat"] - point[0], (s["lon"] - point[1]) * math.cos(math.radians(point[0])))


def _free(day: dict, kind: str | None = None) -> list[tuple]:
    used = {it["slot"] for it in day["items"]}
    return [sl for sl in SLOTS if sl[0] not in used and (kind is None or sl[1] == kind)]


def _open_slots(day: dict, s: dict) -> list[tuple]:
    """Free slots of the stop's kind that it isn't known to be closed for."""
    weekday = day["date"].weekday()
    return [sl for sl in _free(day, s["kind"]) if is_open(s.get("hours"), weekday, sl[2], sl[3]) is not False]


def _best_day(days: list[dict], s: dict) -> dict:
    candidates = ([d for d in days if _open_slots(d, s)] or [d for d in days if _free(d, s["kind"])]
                  or [d for d in days if _free(d)] or days)

    def score(d):
        same_kind = sum(it["kind"] == s["kind"] for it in d["items"])
        located = [it for it in d["items"] if it.get("lat") is not None]
        if s.get("lat") is None or not located:
            return (same_kind, 1, len(d["items"]))
        mid = (sum(it["lat"] for it in located) / len(located), sum(it["lon"] for it in located) / len(located))
        return (same_kind, 0, _dist(s, mid))
    return min(candidates, key=score)


def _place(day: dict, s: dict) -> None:
    """Put a stop in the first free slot of its kind that it's open for, then any free slot of its kind, then any
    free slot at all. Flags it when the hours are known and it's closed for the slot it got."""
    weekday = day["date"].weekday()
    options = _free(day, s["kind"]) or _free(day) or [SLOTS[-1]]
    open_ones = [sl for sl in options if is_open(s.get("hours"), weekday, sl[2], sl[3]) is not False]
    name, _, start, end = (open_ones or options)[0]
    day["items"].append({**s, "slot": name, "start_min": start, "end_min": end,
                         "hours_conflict": not open_ones})
