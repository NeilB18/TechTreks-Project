"""Planning in steps: the ideas list, one stop added to a day, and drafts for only the days asked (no network).

Runs against the in-memory TripEngine and the Django DjangoBackend, so ideas and planning notes survive the database.
"""

from datetime import date

import pytest
from conftest import make_backend

from agent.backend.core.engine import MAX_IDEAS, TripEngine
from agent.backend.protocol import ToolError, dispatch
from agent.travel import osm
from agent.travel.provider import FakeTravel

MEMBERS = [{"id": p, "name": p.title()} for p in ["aarav", "jake", "mia"]]
TRIP = {"id": "t", "start_date": "2027-03-14", "end_date": "2027-03-16", "destination": "Miami"}  # Sun to Tue


@pytest.fixture(params=["memory", "django"])
def b(request, db):
    b = make_backend(request.param)
    b.load_seed({"now": "2027-03-01T12:00:00", "trip": TRIP, "members": MEMBERS})
    return b


def call(b, tool, **args):
    return dispatch(b, tool, {"trip_id": "t", **args})


def ideas(b):
    return [i["name"] for i in b.summary("t")["ideas"]]


def test_an_idea_is_checked_on_the_map_and_kept_until_someone_drops_it(b):
    r = call(b, "save_idea", name="Wynwood Walls", kind="activity", suggested_by="jake")
    assert r["saved"] and r["idea"]["verified"] is True and r["idea"]["maps_url"]
    assert call(b, "save_idea", name="wynwood walls", kind="activity")["already_on_list"]
    missing = call(b, "save_idea", name="Zzqx Imaginary Taco Palace", kind="food")
    assert missing["not_found"] and missing["idea"]["verified"] is False
    assert ideas(b) == ["Wynwood Walls", "Zzqx Imaginary Taco Palace"]
    assert call(b, "get_trip")["ideas"][0]["suggested_by"] == "jake"
    call(b, "save_idea", name="Wynwood Walls", remove=True)  # anyone can drop one
    assert ideas(b) == ["Zzqx Imaginary Taco Palace"]


def test_the_ideas_list_is_capped():
    b = TripEngine(travel=FakeTravel())
    b.load_seed({"trip": TRIP, "members": MEMBERS})
    for i in range(MAX_IDEAS):
        call(b, "save_idea", name=f"Spot {i}", kind="activity")
    with pytest.raises(ToolError, match="full"):
        call(b, "save_idea", name="One more", kind="activity")


def test_one_stop_goes_in_a_free_slot_of_its_kind_that_day(b):
    r = call(b, "add_activity", name="Versailles Restaurant", kind="food", day="2027-03-15")
    assert r["created"] and r["slot"] == "lunch" and r["start"] == "2027-03-15T12:30"
    assert r["verified"] is True and r["maps_url"].startswith("https://www.google.com/maps/search/")
    assert call(b, "add_activity", name="Joe's Stone Crab", kind="food", day="2027-03-15")["slot"] == "dinner"
    full = call(b, "add_activity", name="La Mar", kind="food", day="2027-03-15")
    assert full["created"] is False and full["day_full"]
    assert full["plans_that_day"] == ["Versailles Restaurant", "Joe's Stone Crab"]
    assert len(call(b, "get_trip")["activities"]) == 2  # nothing saved for the full day


def test_a_stop_closed_that_day_isnt_saved():
    class ClosedMondays(FakeTravel):
        def find_place(self, name, city):
            return osm.Place(name, 25.77, -80.19, "tourism/museum", f"{name}, Miami", opening_hours="Tu-Su 10:00-17:00",
                             hours=osm.parse_opening_hours("Tu-Su 10:00-17:00"))
    b = TripEngine(travel=ClosedMondays())
    b.load_seed({"trip": TRIP, "members": MEMBERS})
    assert date(2027, 3, 15).weekday() == 0
    r = call(b, "add_activity", name="Vizcaya Museum", kind="activity", day="2027-03-15")
    assert r["created"] is False and r["closed_then"] and r["opening_hours"] == "Tu-Su 10:00-17:00"
    assert call(b, "add_activity", name="Vizcaya Museum", kind="activity", day="2027-03-16")["created"]


def test_a_stop_without_a_kind_isnt_looked_up():
    class NoLookups(FakeTravel):
        def find_place(self, name, city):
            raise AssertionError("looked up")
    b = TripEngine(travel=NoLookups())
    b.load_seed({"trip": TRIP, "members": MEMBERS})
    r = call(b, "add_activity", name="Flight home", start="2027-03-16T18:00")
    assert r["created"] and "maps_url" not in r
    with pytest.raises(ToolError, match="kind"):
        call(b, "add_activity", name="Somewhere", day="2027-03-15")


def test_an_idea_put_on_a_day_leaves_the_list(b):
    idea = call(b, "save_idea", name="Wynwood Walls", kind="activity", est_cost_cents=0)["idea"]
    r = call(b, "add_activity", idea_id=idea["idea_id"], day="2027-03-14")
    assert r["created"] and r["from_ideas"] and r["slot"] == "morning"
    assert ideas(b) == []
    [a] = call(b, "get_trip")["activities"]
    assert a["name"] == "Wynwood Walls" and a["verified"] is True and a["est_cost_cents"] == 0


def test_a_draft_covers_only_the_days_asked_and_uses_ideas_first(b):
    call(b, "save_idea", name="Wynwood Walls", kind="activity")
    call(b, "add_activity", name="Versailles Restaurant", kind="food", day="2027-03-15")  # Monday lunch is taken
    d = call(b, "generate_itinerary", days=["2027-03-15"], places=[
        {"name": "Joe's Stone Crab", "kind": "food"}, {"name": "Ball & Chain", "kind": "night"},
        {"name": "Versailles Restaurant", "kind": "food"}])
    [day] = d["days"]
    assert day["date"] == "2027-03-15" and d["ideas_used"] == ["Wynwood Walls"]
    assert d["already_on_trip"] == ["Versailles Restaurant"]
    assert {it["name"]: it["slot"] for it in day["items"]} == {
        "Wynwood Walls": "morning", "Joe's Stone Crab": "dinner", "Ball & Chain": "night"}
    saved = call(b, "generate_itinerary", save_draft_id=d["draft_id"])
    assert saved["ideas_scheduled"] == ["Wynwood Walls"] and ideas(b) == []
    assert len(call(b, "get_trip")["activities"]) == 4


def test_a_draft_can_leave_the_ideas_out(b):
    call(b, "save_idea", name="Wynwood Walls", kind="activity")
    d = call(b, "generate_itinerary", days=["2027-03-14"], use_ideas=False,
             places=[{"name": "South Pointe Park", "kind": "activity"}])
    assert [it["name"] for it in d["days"][0]["items"]] == ["South Pointe Park"] and ideas(b) == ["Wynwood Walls"]


def test_a_full_day_cant_be_drafted(b):
    call(b, "add_activity", name="All-day boat trip", start="2027-03-14T09:00", end="2027-03-14T23:59")
    with pytest.raises(ToolError, match="already full"):
        call(b, "generate_itinerary", days=["2027-03-14"], places=[{"name": "Wynwood Walls", "kind": "activity"}])


def test_planning_notes_are_saved(b):
    call(b, "update_trip", changes={"planning_notes": "chill mornings, big on food"})
    assert b.summary("t")["trip"]["planning_notes"] == "chill mornings, big on food"
    with pytest.raises(ToolError, match="planning_notes"):
        call(b, "update_trip", changes={"planning_notes": "x" * 501})
