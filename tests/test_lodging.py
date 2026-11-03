"""Where the group is staying: looked up on the map, saved on the trip, nothing saved if it can't be found (no network).

Runs against the in-memory TripEngine and the Django DjangoBackend.
"""

import pytest
from conftest import make_backend

from agent.backend.core.engine import TripEngine
from agent.backend.protocol import ToolError, dispatch
from agent.travel.provider import FakeTravel

MEMBERS = [{"id": p, "name": p.title()} for p in ["aarav", "jake", "mia"]]
TRIP = {"id": "t", "start_date": "2027-03-14", "end_date": "2027-03-16", "destination": "Miami", "leader": "aarav"}


@pytest.fixture(params=["memory", "django"])
def b(request, db):
    b = make_backend(request.param)
    b.load_seed({"now": "2027-03-01T12:00:00", "trip": TRIP, "members": MEMBERS})
    return b


def lodging(b):
    return b.summary("t")["trip"]["lodging"]


def stay(b, where):
    return dispatch(b, "update_trip", {"trip_id": "t", "changes": {"lodging": where}})


def test_lodging_is_found_on_the_map_and_saved(b):
    r = stay(b, "Freehand Miami")
    assert r["updated"] and "address you saved" in r["next_step"]
    saved = lodging(b)
    assert saved["name"] == "Freehand Miami" and saved["lat"] is not None and saved["address"]
    assert saved["maps_url"].startswith("https://www.google.com/maps/search/")


def test_a_correction_replaces_it_and_empty_clears_it(b):
    stay(b, "Freehand Miami")
    stay(b, "2727 Indian Creek Dr")
    assert lodging(b)["name"] == "2727 Indian Creek Dr"
    stay(b, "")
    assert lodging(b) is None


def test_nothing_is_saved_when_the_map_cant_find_it(b):
    stay(b, "Freehand Miami")
    with pytest.raises(ToolError, match="street address"):
        dispatch(b, "update_trip", {"trip_id": "t", "changes": {"name": "Spring Break", "lodging": "Zzqx Imaginary Taco Palace"}})
    assert lodging(b)["name"] == "Freehand Miami"
    assert b.summary("t")["trip"]["name"] != "Spring Break"  # the whole change waits for a real address


def test_a_map_outage_saves_nothing():
    class Down(FakeTravel):
        def find_place(self, name, city):
            raise RuntimeError("map is down")
    b = TripEngine(travel=Down())
    b.load_seed({"trip": TRIP, "members": MEMBERS})
    with pytest.raises(ToolError, match="Try again"):
        stay(b, "Freehand Miami")
    assert lodging(b) is None


def test_lodging_needs_a_destination():
    b = TripEngine(travel=FakeTravel())
    b.load_seed({"trip": {**TRIP, "destination": None}, "members": MEMBERS})
    with pytest.raises(ToolError, match="destination"):
        stay(b, "Freehand Miami")


def test_a_seed_can_set_lodging():
    b = TripEngine(travel=FakeTravel())
    b.load_seed({"trip": {**TRIP, "lodging": "Freehand Miami"}, "members": MEMBERS})
    assert lodging(b)["name"] == "Freehand Miami" and lodging(b)["lat"] is not None
