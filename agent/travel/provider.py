"""Where travel tips and itinerary ideas come from.

FakeTravel is canned text (tests, demos, no keys). LiveTravel uses Google Places
(places, ratings, price levels) and SerpAPI Google Hotels (lodging prices). It's
picked automatically when GOOGLE_PLACES_API_KEY is set; SERPAPI_KEY is optional.
Any API error falls back to the fake data for that piece, with a note, so the
agent never stalls on a bad response.
"""

import logging
import os
from datetime import date

from agent.travel import places, serp

log = logging.getLogger(__name__)

FAKE_TIPS = {
    "budget": {"lodging": "Hostel or a shared room a bit outside the center",
               "food": "Street food, food trucks and grocery-store breakfasts",
               "activities": "Free beach days, walking tours and public parks",
               "saving_tips": "Use public transit or bikes instead of rideshares"},
    "mid": {"lodging": "Shared Airbnb in a central neighborhood",
            "food": "Casual local spots plus one nice group dinner",
            "activities": "One paid group activity (boat tour, museum) plus free days",
            "saving_tips": "Book the big activity early and split groceries"},
    "splurge": {"lodging": "Hotel in the main strip",
                "food": "Sit-down dinners most nights",
                "activities": "Several paid activities and a night out",
                "saving_tips": "Bundle bookings and watch for group discounts"},
}
FAKE_ITINERARY_ITEMS = [
    ("Beach day", "Main beach", 0),
    ("Walking tour", "Old town", 2000),
    ("Group dinner", "Local restaurant", 4500),
    ("Boat tour", "Marina", 10000),
    ("Museum visit", "City museum", 2500),
    ("Night out", "Downtown", 6000),
]
# Google price levels for each tier, and a rough per-person cost for an item at that level.
TIER_PRICE_LEVELS = {"budget": ["PRICE_LEVEL_INEXPENSIVE"], "mid": ["PRICE_LEVEL_MODERATE"],
                     "splurge": ["PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"]}
EST_COST_CENTS = {"PRICE_LEVEL_FREE": 0, "PRICE_LEVEL_INEXPENSIVE": 1500, "PRICE_LEVEL_MODERATE": 3000,
                  "PRICE_LEVEL_EXPENSIVE": 6000, "PRICE_LEVEL_VERY_EXPENSIVE": 10000}
LODGING_SHARE = 0.4  # assume lodging is ~40% of a person's trip budget, rooms shared by 2


def tier_level(multiplier: float) -> str:
    return "budget" if multiplier < 0.75 else "mid" if multiplier < 1.25 else "splurge"


class FakeTravel:
    source = "fake"

    def tips(self, destination: str, tier: dict, start: str | None, end: str | None) -> dict:
        return {**FAKE_TIPS[tier_level(tier["multiplier"])], "source": "fake"}

    def itinerary_items(self, destination: str, n: int, constraints: str | None) -> list[tuple[str, str, int]]:
        return [(name, f"{loc}, {destination}", cost)
                for name, loc, cost in (FAKE_ITINERARY_ITEMS[i % len(FAKE_ITINERARY_ITEMS)] for i in range(n))]


class LiveTravel:
    source = "live"

    def __init__(self, places_key: str, serp_key: str | None = None):
        self.places_key, self.serp_key = places_key, serp_key
        self.fake = FakeTravel()

    def tips(self, destination: str, tier: dict, start: str | None, end: str | None) -> dict:
        level = tier_level(tier["multiplier"])
        out = {**self.fake.tips(destination, tier, start, end), "source": "live", "notes": []}
        try:
            food = places.search(self.places_key, f"restaurants in {destination}", TIER_PRICE_LEVELS[level], page_size=3)
            out["food"] = [_place_line(p) for p in food] or out["food"]
            things = places.search(self.places_key, f"top things to do in {destination}",
                                   included_type="tourist_attraction", page_size=3)
            out["activities"] = [_place_line(p) for p in things] or out["activities"]
        except Exception as e:  # noqa: BLE001 - any API problem falls back to canned tips
            log.warning("Places lookup failed for %s: %s", destination, e)
            out["notes"].append("Places lookup failed; food/activity tips are general.")
        if self.serp_key and start and end:
            try:
                nights = max((date.fromisoformat(end) - date.fromisoformat(start)).days, 1)
                room_cap = round(tier["budget_cents"] * LODGING_SHARE * 2 / nights / 100)  # whole dollars
                stays = serp.hotels(self.serp_key, destination, start, end, max_price=room_cap)
                if stays:
                    out["lodging"] = [f"{s['name']} (~${s['per_night_cents'] // 100}/night per room"
                                      f"{', ' + str(round(s['rating'], 1)) + '★' if s.get('rating') else ''})"
                                      for s in stays]
            except Exception as e:  # noqa: BLE001
                log.warning("Hotel lookup failed for %s: %s", destination, e)
                out["notes"].append("Hotel lookup failed; lodging tip is general.")
        return out

    def itinerary_items(self, destination: str, n: int, constraints: str | None) -> list[tuple[str, str, int]]:
        try:
            size = min(max(n // 2 + 1, 3), 20)
            things = places.search(self.places_key, f"top things to do in {destination} {constraints or ''}".strip(),
                                   page_size=size)
            food = places.search(self.places_key, f"popular restaurants in {destination}", page_size=size)
        except Exception as e:  # noqa: BLE001
            log.warning("Places itinerary lookup failed for %s: %s", destination, e)
            return self.fake.itinerary_items(destination, n, constraints)
        if not things or not food:
            return self.fake.itinerary_items(destination, n, constraints)
        items = []
        for i in range(n):  # daytime activity, then dinner, alternating
            p = things[(i // 2) % len(things)] if i % 2 == 0 else food[(i // 2) % len(food)]
            items.append((p["name"], p["address"] or destination,
                          EST_COST_CENTS.get(p.get("price_level"), 0 if i % 2 == 0 else 3000)))
        return items


def _place_line(p: dict) -> str:
    price = {"PRICE_LEVEL_INEXPENSIVE": "$", "PRICE_LEVEL_MODERATE": "$$", "PRICE_LEVEL_EXPENSIVE": "$$$",
             "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$"}.get(p.get("price_level"))
    details = [d for d in (price, f"{p['rating']}★" if p.get("rating") else None, p.get("address")) if d]
    return f"{p['name']} ({', '.join(details)})" if details else p["name"]


def get_provider():
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    return LiveTravel(key, os.environ.get("SERPAPI_KEY")) if key else FakeTravel()
