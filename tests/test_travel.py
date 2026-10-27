"""Live travel data (Google Places + SerpAPI), tested with recorded sample responses: no network."""

import json
from pathlib import Path

import pytest

from agent.backend.core.engine import TripEngine
from agent.travel import places, provider, serp
from agent.travel.provider import FakeTravel, LiveTravel, get_provider

FIXTURES = Path(__file__).parent / "fixtures" / "travel"


class Resp:
    def __init__(self, name=None, status=200):
        self.status_code = status
        self._data = json.loads((FIXTURES / name).read_text()) if name else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


@pytest.fixture
def api(monkeypatch):
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "body": json, "headers": headers})
        return Resp("places_restaurants.json" if "restaurants" in json["textQuery"] else "places_things.json")

    def get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params})
        return Resp("serp_hotels.json")

    monkeypatch.setattr(places.requests, "post", post)
    monkeypatch.setattr(serp.requests, "get", get)
    return calls


def test_places_request_shape_and_parsing(api):
    out = places.search("KEY", "restaurants in Miami", ["PRICE_LEVEL_MODERATE"], page_size=3)
    req = api[0]
    assert req["url"] == "https://places.googleapis.com/v1/places:searchText"
    assert req["headers"]["X-Goog-Api-Key"] == "KEY" and " " not in req["headers"]["X-Goog-FieldMask"]
    assert req["body"] == {"textQuery": "restaurants in Miami", "pageSize": 3, "priceLevels": ["PRICE_LEVEL_MODERATE"]}
    assert out[0] == {"name": "La Mar by Gastón Acurio", "address": "500 Brickell Key Dr, Miami, FL 33131, USA",
                      "rating": 4.6, "ratings": 3120, "price_level": "PRICE_LEVEL_MODERATE",
                      "maps_url": "https://maps.google.com/?cid=1"}


def test_serp_hotels_request_and_parsing(api):
    out = serp.hotels("SKEY", "Miami", "2027-03-14", "2027-03-18", max_price=300)
    params = api[0]["params"]
    assert params["engine"] == "google_hotels" and params["check_in_date"] == "2027-03-14"
    assert params["max_price"] == 300 and params["api_key"] == "SKEY"
    assert [h["name"] for h in out] == ["Freehand Miami", "South Beach 2BR"]  # unpriced one dropped
    assert out[0]["per_night_cents"] == 14200


def test_live_tips_use_real_places_and_hotels(api):
    tips = LiveTravel("KEY", "SKEY").tips("Miami", {"multiplier": 1.1, "budget_cents": 91700},
                                          "2027-03-14", "2027-03-18")
    assert tips["source"] == "live" and tips["notes"] == []
    assert tips["food"][0].startswith("La Mar by Gastón Acurio ($$, 4.6★")
    assert tips["activities"][0].startswith("Wynwood Walls (4.6★")
    assert tips["lodging"][0] == "Freehand Miami (~$142/night per room, 4.2★)"
    # 40% of ~$917 per person, rooms for 2, 4 nights -> about $183/night cap
    assert [c for c in api if "params" in c][0]["params"]["max_price"] == 183


def test_api_failure_falls_back_with_a_note(monkeypatch):
    monkeypatch.setattr(places.requests, "post", lambda *a, **k: Resp(status=403))
    tips = LiveTravel("BADKEY").tips("Miami", {"multiplier": 1, "budget_cents": 80000}, None, None)
    assert tips["food"] == provider.FAKE_TIPS["mid"]["food"]
    assert tips["notes"] == ["Places lookup failed; food/activity tips are general."]
    items = LiveTravel("BADKEY").itinerary_items("Miami", 4, None)
    assert items == FakeTravel().itinerary_items("Miami", 4, None)


def test_itinerary_alternates_activities_and_dinners(api):
    b = TripEngine(travel=LiveTravel("KEY"))
    b.load_seed({"trip": {"id": "t", "destination": "Miami", "start_date": "2027-03-14", "end_date": "2027-03-15"},
                 "members": [{"id": "a", "name": "A"}]})
    d = b.generate_itinerary(trip_id="t")
    assert d["source"] == "live"
    names = [i["name"] for day in d["days"] for i in day["items"]]
    assert names == ["Wynwood Walls", "La Mar by Gastón Acurio", "Vizcaya Museum & Gardens", "Versailles Restaurant"]
    assert d["days"][0]["items"][1]["est_cost_cents"] == 3000


def test_provider_switch(monkeypatch):
    assert isinstance(get_provider(), FakeTravel)  # conftest clears the keys
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "k")
    assert isinstance(get_provider(), LiveTravel)
