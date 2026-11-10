"""The map is off (Nominatim turned off, Nov 10 2026): no request goes out, and planning still works without it."""

import pytest
import requests

from agent.backend.core.engine import TripEngine
from agent.backend.protocol import ToolError, dispatch
from agent.travel import nearby, osm
from agent.travel.provider import LiveTravel, NoMapTravel

MEMBERS = [{"id": p, "name": p.title()} for p in ["aarav", "jake"]]
TRIP = {"id": "t", "start_date": "2027-03-14", "end_date": "2027-03-16", "destination": "Miami"}


@pytest.fixture
def no_network(monkeypatch):
    def get(*a, **kw):
        raise AssertionError("a map request went out")
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(osm.requests, "get", get)
    monkeypatch.setattr(osm, "_cache", {})
    monkeypatch.setattr(osm, "_area_cache", {})


@pytest.fixture(params=[NoMapTravel, lambda: LiveTravel("KEY")], ids=["default", "google-key"])
def b(request, no_network):
    b = TripEngine(travel=request.param())
    b.load_seed({"now": "2027-03-01T12:00:00", "trip": TRIP, "members": MEMBERS})
    return b


def test_nominatim_itself_refuses_before_any_request(no_network):
    assert osm.ENABLED is False
    with pytest.raises(osm.MapOff):
        osm.lookup("Versailles Restaurant", "Miami")
    with pytest.raises(osm.MapOff):
        nearby.search("pizza", 25.8, -80.13, 1600)


def test_stops_are_saved_unchecked_without_flagging_the_map(b):
    r = dispatch(b, "add_activity", {"trip_id": "t", "name": "Wynwood Walls", "kind": "activity", "day": "2027-03-14"})
    assert r["created"] and not r["not_found"] and not r["map_check_failed"]
    act = next(a for a in b.summary("t")["activities"] if a["name"] == "Wynwood Walls")
    assert act["verified"] is None and act["lat"] is None

    d = dispatch(b, "generate_itinerary", {"trip_id": "t", "days": ["2027-03-15"],
                                           "places": [{"name": "Versailles Restaurant", "kind": "food"},
                                                      {"name": "Vizcaya Museum and Gardens", "kind": "activity"}]})
    assert d["not_found"] == [] and d["map_check_failed"] == []
    stops = [i for day in d["days"] for i in day["items"]]
    assert stops and all(i["maps_url"].startswith("https://www.google.com/maps/search/") for i in stops)

    idea = dispatch(b, "save_idea", {"trip_id": "t", "name": "Joe's Stone Crab", "kind": "food"})
    assert idea["saved"] and not idea["map_check_failed"] and idea["idea"]["verified"] is None


def test_nearby_search_and_lodging_say_theyre_off(b):
    with pytest.raises(ToolError, match="Nearby search is off"):
        dispatch(b, "find_nearby", {"trip_id": "t", "what": "pizza", "near": "Wynwood Walls"})
    with pytest.raises(ToolError, match="off for now"):
        dispatch(b, "update_trip", {"trip_id": "t", "changes": {"lodging": "Freehand Miami"}})
    assert b.summary("t")["trip"]["lodging"] is None
