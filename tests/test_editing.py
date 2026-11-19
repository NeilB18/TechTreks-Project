"""Editing saved plans: removing one (ideas go back on the list), and moving one to another day, which keeps its
clock time or slot and still asks before two plans share an exact time.

Runs against the in-memory TripEngine and the Django DjangoBackend.
"""

import pytest
from conftest import make_backend

from agent.backend.protocol import ToolError, dispatch

MEMBERS = [{"id": p, "name": p.title()} for p in ["aarav", "jake", "mia"]]
TRIP = {"id": "t", "start_date": "2027-03-14", "end_date": "2027-03-16", "destination": "Miami"}  # Sun to Tue
SUN, MON = "2027-03-14", "2027-03-15"


@pytest.fixture(params=["memory", "django"])
def b(request, db):
    b = make_backend(request.param)
    b.load_seed({"now": "2027-03-01T12:00:00", "trip": TRIP, "members": MEMBERS})
    return b


def call(b, tool, **args):
    return dispatch(b, tool, {"trip_id": "t", **args})


def test_remove_a_saved_activity_and_ideas_go_back_on_the_list(b):
    idea = call(b, "save_idea", name="Wynwood Walls", est_cost_cents=2000)["idea"]
    a = call(b, "add_activity", idea_id=idea["idea_id"], day=SUN)["activity_id"]
    other = call(b, "add_activity", name="Versailles Restaurant", day=SUN, slot="lunch")["activity_id"]
    r = call(b, "remove_activity", activity_id=a)
    assert r["removed"] and r["back_on_ideas"]
    assert [(i["name"], i["est_cost_cents"]) for i in call(b, "get_trip")["ideas"]] == [("Wynwood Walls", 2000)]
    assert call(b, "remove_activity", activity_id=other)["back_on_ideas"] is False
    assert call(b, "get_trip")["activities"] == []
    with pytest.raises(ToolError, match="No activity"):
        call(b, "remove_activity", activity_id=a)


def test_moving_keeps_the_clock_time_and_how_long_it_lasts(b):
    a = call(b, "add_activity", name="Joe's Stone Crab", start=f"{SUN}T19:00", end=f"{SUN}T21:00")["activity_id"]
    r = call(b, "add_activity", activity_id=a, day=MON)
    assert r["updated"] and (r["start"], r["end"]) == (f"{MON}T19:00", f"{MON}T21:00")


def test_moving_keeps_the_slot_or_just_the_day(b):
    lunch = call(b, "add_activity", name="Versailles", day=SUN, slot="lunch")["activity_id"]
    beach = call(b, "add_activity", name="Beach day", day=SUN)["activity_id"]
    assert call(b, "add_activity", activity_id=lunch, day=MON)["slot"] == "lunch"
    r = call(b, "add_activity", activity_id=beach, day=MON)
    assert r["start"] == MON and r["slot"] is None
    later = call(b, "add_activity", name="Somewhere", start=None)["activity_id"]  # not on a day yet
    assert call(b, "add_activity", activity_id=later, day=SUN)["start"] == SUN


def test_moving_onto_the_same_clock_time_asks_first(b):
    call(b, "add_activity", name="Boat tour", start=f"{MON}T14:00")
    a = call(b, "add_activity", name="Wynwood Walls", start=f"{SUN}T14:00")["activity_id"]
    r = call(b, "add_activity", activity_id=a, day=MON)
    assert r["updated"] is False and r["same_time_as"] == ["Boat tour"]
    assert call(b, "get_trip")["activities"][1]["start"] == f"{SUN}T14:00"  # nothing changed
    assert call(b, "add_activity", activity_id=a, day=MON, confirm_same_time=True)["start"] == f"{MON}T14:00"


def test_editing_other_fields_never_asks(b):
    call(b, "add_activity", name="Boat tour", start=f"{MON}T14:00")
    a = call(b, "add_activity", name="Wynwood Walls", start=f"{MON}T14:00", confirm_same_time=True)["activity_id"]
    assert call(b, "add_activity", activity_id=a, est_cost_cents=1500)["updated"]


def test_a_plan_in_a_slot_takes_no_clock_end_time(b):
    lunch = call(b, "add_activity", name="Versailles", day=SUN, slot="lunch")["activity_id"]
    with pytest.raises(ToolError, match="no clock times"):
        call(b, "add_activity", activity_id=lunch, end=f"{SUN}T14:00")
    # A clock start replaces the slot, and then an end time is fine.
    moved = call(b, "add_activity", activity_id=lunch, start=f"{SUN}T12:30", end=f"{SUN}T14:00")
    assert (moved["slot"], moved["end"]) == (None, f"{SUN}T14:00")


def test_an_old_idea_keeps_its_location_on_a_day():
    from agent.backend.core.engine import TripEngine
    e = TripEngine()
    e.load_seed({"now": "2027-03-01T12:00:00", "trip": TRIP, "members": MEMBERS})
    # Saved before the planning cut, with a location; new ideas don't have one.
    e._trip("t").ideas.append({"idea_id": "i1", "name": "Wynwood Walls", "location": "Wynwood", "est_cost_cents": 0,
                               "suggested_by": None})
    a = e.add_activity(trip_id="t", idea_id="i1", day=MON)["activity_id"]
    assert next(x for x in e.summary("t")["activities"] if x["activity_id"] == a)["location"] == "Wynwood"
