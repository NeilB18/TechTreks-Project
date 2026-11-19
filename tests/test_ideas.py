"""The trip's calendar: plans with just a day, a slot or a clock time, the "are you sure?" for the same clock time,
and the ideas list. Nothing is looked up anywhere.

Runs against the in-memory TripEngine and the Django DjangoBackend, so slots and ideas survive the database.
"""

import pytest
from conftest import make_backend

from agent.backend.core.engine import MAX_IDEAS, TripEngine
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


def ideas(b):
    return [i["name"] for i in b.summary("t")["ideas"]]


def plans(b):
    return {a["name"]: (a["start"], a["slot"]) for a in call(b, "get_trip")["activities"]}


def test_a_plan_with_just_a_day_gets_no_time(b):
    r = call(b, "add_activity", name="Wynwood Walls", day=MON)
    assert r["created"] and r["start"] == MON and r["slot"] is None and r["end"] is None
    assert plans(b) == {"Wynwood Walls": (MON, None)}


def test_a_named_slot_is_saved_and_any_number_can_share_it(b):
    call(b, "add_activity", name="Versailles Restaurant", day=SUN, slot="lunch")
    r = call(b, "add_activity", name="La Mar", day=SUN, slot="lunch")
    assert r["created"] and r["slot"] == "lunch" and r["start"] == SUN
    assert plans(b) == {"Versailles Restaurant": (SUN, "lunch"), "La Mar": (SUN, "lunch")}


def test_a_clock_time_is_saved_as_given(b):
    r = call(b, "add_activity", name="Boat tour", start=f"{MON}T14:00", est_cost_cents=6000)
    assert r["created"] and r["start"] == f"{MON}T14:00" and r["slot"] is None


def test_the_same_clock_time_waits_for_a_yes(b):
    call(b, "add_activity", name="Wynwood Walls", start=f"{MON}T12:00")
    r = call(b, "add_activity", name="Boat tour", start=f"{MON}T12:00")
    assert r["created"] is False and r["same_time_as"] == ["Wynwood Walls"] and r["at"] == f"{MON}T12:00"
    assert list(plans(b)) == ["Wynwood Walls"]  # nothing saved yet
    assert call(b, "add_activity", name="Boat tour", start=f"{MON}T12:00", confirm_same_time=True)["created"]
    assert len(plans(b)) == 2


def test_only_an_exact_clock_time_counts(b):
    call(b, "add_activity", name="Wynwood Walls", start=f"{MON}T12:00")
    assert call(b, "add_activity", name="Lunch", start=f"{MON}T12:30")["created"]
    assert call(b, "add_activity", name="Versailles", day=MON, slot="lunch")["created"]  # a slot isn't a clock time
    assert call(b, "add_activity", name="Beach", day=MON)["created"]
    assert call(b, "add_activity", name="Wynwood again", start=f"{SUN}T12:00")["created"]  # another day


def test_bad_slots_are_refused(b):
    with pytest.raises(ToolError, match="slot must be one of"):
        call(b, "add_activity", name="Brunch", day=SUN, slot="brunch")
    with pytest.raises(ToolError, match="not both"):
        call(b, "add_activity", name="Brunch", start=f"{SUN}T11:00", slot="lunch")
    with pytest.raises(ToolError, match="needs a day"):
        call(b, "add_activity", name="Brunch", slot="lunch")
    with pytest.raises(ToolError, match="name"):
        call(b, "add_activity", day=SUN)


def test_a_slot_or_a_time_can_be_given_later(b):
    a = call(b, "add_activity", name="Joe's Stone Crab", day=SUN)["activity_id"]
    assert call(b, "add_activity", activity_id=a, slot="dinner")["slot"] == "dinner"
    assert plans(b)["Joe's Stone Crab"] == (SUN, "dinner")
    r = call(b, "add_activity", activity_id=a, start=f"{SUN}T19:30")
    assert r["start"] == f"{SUN}T19:30" and r["slot"] is None  # a clock time replaces the slot


def test_an_idea_is_kept_until_someone_drops_it(b):
    r = call(b, "save_idea", name="Wynwood Walls", suggested_by="jake")
    assert r["saved"] and r["idea"] == {"idea_id": "i1", "name": "Wynwood Walls", "est_cost_cents": None,
                                        "suggested_by": "jake"}
    assert call(b, "save_idea", name="wynwood walls")["already_on_list"]
    call(b, "save_idea", name="Joe's Stone Crab", est_cost_cents=7000)
    assert ideas(b) == ["Wynwood Walls", "Joe's Stone Crab"]
    assert call(b, "get_trip")["ideas"][0]["suggested_by"] == "jake"
    call(b, "save_idea", name="Wynwood Walls", remove=True)  # anyone can drop one
    assert ideas(b) == ["Joe's Stone Crab"]
    with pytest.raises(ToolError, match="needs a name"):
        call(b, "save_idea", name="  ")


def test_the_ideas_list_is_capped():
    b = TripEngine()
    b.load_seed({"trip": TRIP, "members": MEMBERS})
    for i in range(MAX_IDEAS):
        call(b, "save_idea", name=f"Spot {i}")
    with pytest.raises(ToolError, match="full"):
        call(b, "save_idea", name="One more")


def test_ideas_dont_need_a_destination():
    b = TripEngine()
    b.load_seed({"trip": {**TRIP, "destination": None}, "members": MEMBERS})
    assert call(b, "save_idea", name="Somewhere warm")["saved"]


def test_an_idea_put_on_a_day_leaves_the_list(b):
    idea = call(b, "save_idea", name="Wynwood Walls", est_cost_cents=0)["idea"]
    r = call(b, "add_activity", idea_id=idea["idea_id"], day=SUN, slot="morning")
    assert r["created"] and r["from_ideas"] and r["slot"] == "morning"
    assert ideas(b) == []
    [a] = call(b, "get_trip")["activities"]
    assert a["name"] == "Wynwood Walls" and a["est_cost_cents"] == 0 and a["from_idea"]


def test_the_summary_has_no_map_or_draft_fields(b):
    call(b, "add_activity", name="Wynwood Walls", day=MON)
    s = b.summary("t")
    assert not {"planning_notes", "home_city"} & set(s["trip"])
    assert set(s["activities"][0]) >= {"slot", "from_idea"} and not {"lat", "lon", "verified", "kind"} & set(
        s["activities"][0])
    assert "itinerary_drafts" not in call(b, "get_trip")
    with pytest.raises(ToolError, match="Can't change"):
        call(b, "update_trip", changes={"home_city": "Atlanta"})
    with pytest.raises(ToolError, match="Unknown leader_approval"):
        call(b, "update_trip", changes={"leader_approval": ["itinerary_saves"]})
