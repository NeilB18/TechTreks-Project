"""Nearby search: Nominatim area searches (recorded answers, no network) and the find_nearby tool."""

import json
from pathlib import Path

import pytest
import requests
from conftest import make_backend

from agent.backend.core.engine import TripEngine
from agent.backend.protocol import ToolError, dispatch
from agent.travel import nearby, osm
from agent.travel.provider import FakeTravel

FIXTURES = Path(__file__).parent / "fixtures" / "osm"
FREEHAND = (25.8037, -80.1270)  # where the nearby_*.json answers were searched from (1600 m), Nov 3 2026
RECORDED = {"restaurant": "nearby_restaurant.json", "fast food": "nearby_fast_food.json", "cafe": "nearby_cafe.json"}
MEMBERS = [{"id": p, "name": p.title()} for p in ["aarav", "jake", "mia"]]
TRIP = {"id": "t", "start_date": "2027-03-14", "end_date": "2027-03-16", "destination": "Miami"}


class Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


@pytest.fixture
def nominatim(monkeypatch):
    """Recorded area answers by phrase (anything else finds nothing); records each request."""
    calls = []

    def get(url, params, headers, timeout):
        calls.append({"url": url, "params": params, "headers": headers})
        name = RECORDED.get(params["q"])
        return Resp(json.loads((FIXTURES / name).read_text(encoding="utf-8")) if name else [])
    monkeypatch.setattr(osm.requests, "get", get)
    monkeypatch.setattr(osm, "_area_cache", {})
    monkeypatch.setattr(osm, "MIN_INTERVAL_S", 0)
    return calls


# ------------------------------------------------------------------ the search
def test_a_food_type_searches_restaurants_and_fast_food_and_keeps_matches(nominatim):
    places = nearby.search("pizza", *FREEHAND, 1600)
    assert {"Piola Italian Restaurant - Miami Beach", "41 Pizza & Bakery", "Domino's", "Pizza Bar"} <= {p["name"] for p in places}
    assert all("pizza" in (p["cuisine"] or "") + p["name"].lower() for p in places)  # Piola only by its cuisine tag
    assert [c["params"]["q"] for c in nominatim] == ["restaurant", "fast food"] * 4  # one box per quarter
    assert len({c["params"]["viewbox"] for c in nominatim}) == 4
    req = nominatim[0]["params"]
    assert req["bounded"] == 1 and req["addressdetails"] == 1 and len(req["viewbox"].split(",")) == 4
    assert "TechTreks" in nominatim[0]["headers"]["User-Agent"]  # the usage policy wants the app named


def test_a_category_word_is_one_search_with_addresses(nominatim):
    cafes = nearby.search("Coffee", *FREEHAND, 1600)
    assert [c["params"]["q"] for c in nominatim] == ["cafe"] and len(cafes) >= 10
    assert any(p["street"] for p in cafes) and "Starbucks" in {p["name"] for p in cafes}
    nearby.search("coffee", *FREEHAND, 1600)
    assert len(nominatim) == 1  # cached


def test_words_are_normalized_and_checked():
    assert nearby.normalize(" Tacos ") == "taco" and nearby.normalize("Ice Cream") == "ice cream"
    assert nearby.normalize("glass") == "glass" and nearby.normalize("bars") == "bar"
    assert nearby.normalize('pizza"];out;') is None and nearby.normalize("") is None
    with pytest.raises(ValueError):
        nearby.search("pizza!!", *FREEHAND, 1600)


def test_distances_read_like_a_person_would_say_them():
    assert nearby.describe_distance(1609.344) == ("1.0 mi", "about a 25 min walk")
    assert nearby.describe_distance(50) == ("under 0.1 mi", "about a 1 min walk")
    assert round(nearby.distance_m(25.8037, -80.1270, 25.8037 + 0.01, -80.1270)) == 1112


# ------------------------------------------------------------------ the tool
@pytest.fixture(params=["memory", "django"])
def b(request, db):
    b = make_backend(request.param)
    b.load_seed({"now": "2027-03-01T12:00:00", "trip": {**TRIP, "lodging": "Freehand Miami"}, "members": MEMBERS})
    return b


def find(b, **args):
    return dispatch(b, "find_nearby", {"trip_id": "t", **args})


def test_closest_five_from_the_lodging(b):
    r = find(b, what="pizza")
    assert r["near"] == "Freehand Miami" and r["within"] == "1 mi" and r["more_found"] == 2
    assert [p["name"] for p in r["results"]] == [f"Pizza Spot {i}" for i in range(1, 6)]
    assert r["results"][0]["distance"] == "0.1 mi" and r["results"][0]["walk"] == "about a 3 min walk"
    assert r["results"][0]["opening_hours"] == "Mo-Su 11:00-23:00"
    assert r["results"][0]["maps_url"].startswith("https://www.google.com/maps/search/") and "Collins" in r["results"][0]["maps_url"]
    assert r["credit"] == "© OpenStreetMap contributors" and "no ratings" in r["note"]


def test_a_smaller_radius_and_a_named_starting_point(b):
    r = find(b, what="coffee", radius_m=400)
    assert len(r["results"]) == 2 and r["within"] == "0.2 mi" and r["more_found"] == 0
    assert find(b, what="coffee", near="Wynwood Walls")["near"] == "Wynwood Walls"


def test_nothing_found_offers_to_look_farther(b):
    r = find(b, what="zzqx")
    assert r["results"] == [] and "farther" in r["next_step"]


def test_bad_requests_are_refused(b):
    with pytest.raises(ToolError, match="short word"):
        find(b, what='pizza"];out;')
    with pytest.raises(ToolError, match="radius_m"):
        find(b, what="pizza", radius_m=20000)
    with pytest.raises(ToolError, match="Couldn't find"):
        find(b, what="pizza", near="Zzqx Imaginary Taco Palace")


def test_no_lodging_asks_where_they_are_staying():
    b = TripEngine(travel=FakeTravel())
    b.load_seed({"trip": TRIP, "members": MEMBERS})
    with pytest.raises(ToolError, match="where the group is staying"):
        find(b, what="pizza")


def test_a_busy_map_gets_a_friendly_error():
    class Busy(FakeTravel):
        def find_nearby(self, what, lat, lon, radius_m):
            raise requests.HTTPError("503")
    b = TripEngine(travel=Busy())
    b.load_seed({"trip": {**TRIP, "lodging": "Freehand Miami"}, "members": MEMBERS})
    with pytest.raises(ToolError, match="busy"):
        find(b, what="pizza")


def test_real_map_data_comes_back_closest_first_within_a_mile(nominatim):
    class Recorded(FakeTravel):
        def find_place(self, name, city):
            p = super().find_place(name, city)
            p.lat, p.lon = FREEHAND
            return p

        def find_nearby(self, what, lat, lon, radius_m):
            return nearby.search(what, lat, lon, radius_m)
    b = TripEngine(travel=Recorded())
    b.load_seed({"trip": {**TRIP, "lodging": "Freehand Miami"}, "members": MEMBERS})
    r = find(b, what="pizza")
    assert [(p["name"], p["distance"]) for p in r["results"]] == [
        ("Piola Italian Restaurant - Miami Beach", "0.7 mi"), ("41 Pizza & Bakery", "0.7 mi"),
        ("Domino's", "0.8 mi"), ("Pizza Bar", "0.9 mi")]  # Spris (1.1 mi) is in the search box but past a mile
