"""Editing plans: one change to an unsaved draft, removing a saved activity, moving one to another day (no network).

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


def draft(b):
    """A Sunday draft: Wynwood Walls in the morning, Versailles for lunch, Joe's Stone Crab for dinner."""
    return call(b, "generate_itinerary", days=[SUN], places=[
        {"name": "Wynwood Walls", "kind": "activity"}, {"name": "Versailles Restaurant", "kind": "food"},
        {"name": "Joe's Stone Crab", "kind": "food", "est_cost_cents": 7000}])["draft_id"]


def slots(result, day=SUN):
    return {it["name"]: it["slot"] for d in result["days"] if d["date"] == day for it in d["items"]}


def test_drop_a_stop(b):
    d = draft(b)
    r = call(b, "edit_draft", draft_id=d, action="drop", stop="wynwood walls")
    assert r["changed"] and r["draft_id"] == d and "Wynwood Walls" not in slots(r)


def test_swap_keeps_the_slot_when_it_fits(b):
    d = draft(b)
    r = call(b, "edit_draft", draft_id=d, action="swap", stop="Joe's Stone Crab",
             place={"name": "La Mar by Gastón Acurio", "kind": "food", "est_cost_cents": 6000})
    assert slots(r) == {"Wynwood Walls": "morning", "Versailles Restaurant": "lunch", "La Mar by Gastón Acurio": "dinner"}
    assert r["not_found"] is False


def test_swap_for_another_kind_goes_in_a_free_slot_of_that_kind(b):
    d = draft(b)
    r = call(b, "edit_draft", draft_id=d, action="swap", stop="Wynwood Walls",
             place={"name": "Ball & Chain", "kind": "night"})
    assert slots(r) == {"Versailles Restaurant": "lunch", "Joe's Stone Crab": "dinner", "Ball & Chain": "night"}


def test_move_a_stop_to_a_day_the_draft_didnt_cover(b):
    d = draft(b)
    r = call(b, "edit_draft", draft_id=d, action="move", stop="Joe's Stone Crab", day=MON)
    assert "Joe's Stone Crab" not in slots(r) and slots(r, MON) == {"Joe's Stone Crab": "dinner"}  # keeps its slot
    assert [day["date"] for day in r["days"]] == [SUN, MON]


def test_add_a_stop_then_save_keeps_kinds(b):
    d = draft(b)
    r = call(b, "edit_draft", draft_id=d, action="add", day=SUN, place={"name": "Ball & Chain", "kind": "night"})
    assert slots(r)["Ball & Chain"] == "night"
    call(b, "generate_itinerary", save_draft_id=d)
    kinds = {a["name"]: a["kind"] for a in call(b, "get_trip")["activities"]}
    assert kinds == {"Wynwood Walls": "activity", "Versailles Restaurant": "food", "Joe's Stone Crab": "food",
                     "Ball & Chain": "night"}


def test_no_free_slot_changes_nothing(b):
    d = draft(b)
    r = call(b, "edit_draft", draft_id=d, action="add", day=SUN, place={"name": "La Mar", "kind": "food"})
    assert r["changed"] is False and r["day_full"]
    assert len(call(b, "get_trip")["itinerary_drafts"]) == 1
    again = call(b, "edit_draft", draft_id=d, action="drop", stop="Versailles Restaurant")
    assert set(slots(again)) == {"Wynwood Walls", "Joe's Stone Crab"}  # the failed add left the draft as it was


def test_bad_edits_are_refused(b):
    d = draft(b)
    with pytest.raises(ToolError, match="No stop"):
        call(b, "edit_draft", draft_id=d, action="drop", stop="Museum")
    with pytest.raises(ToolError, match="already"):
        call(b, "edit_draft", draft_id=d, action="add", day=MON, place={"name": "Wynwood Walls", "kind": "activity"})
    with pytest.raises(ToolError, match="day must be"):
        call(b, "edit_draft", draft_id=d, action="move", stop="Wynwood Walls", day="2027-04-01")
    with pytest.raises(ToolError, match="No draft"):
        call(b, "edit_draft", draft_id="d99", action="drop", stop="Wynwood Walls")


def test_remove_a_saved_activity_and_ideas_go_back_on_the_list(b):
    idea = call(b, "save_idea", name="Wynwood Walls", kind="activity")["idea"]
    a = call(b, "add_activity", idea_id=idea["idea_id"], day=SUN)["activity_id"]
    other = call(b, "add_activity", name="Versailles Restaurant", kind="food", day=SUN)["activity_id"]
    r = call(b, "remove_activity", activity_id=a)
    assert r["removed"] and r["back_on_ideas"]
    assert [i["name"] for i in b.summary("t")["ideas"]] == ["Wynwood Walls"]
    assert call(b, "remove_activity", activity_id=other)["back_on_ideas"] is False
    assert call(b, "get_trip")["activities"] == []
    with pytest.raises(ToolError, match="No activity"):
        call(b, "remove_activity", activity_id=a)


def test_move_a_saved_activity_keeps_its_slot(b):
    a = call(b, "add_activity", name="Joe's Stone Crab", kind="food", start=f"{SUN}T19:00", end=f"{SUN}T21:00")
    r = call(b, "add_activity", activity_id=a["activity_id"], day=MON)
    assert r["updated"] and r["start"] == f"{MON}T19:00"  # still dinner
    call(b, "add_activity", name="Versailles Restaurant", kind="food", day=SUN)
    call(b, "add_activity", name="La Mar", kind="food", day=SUN)
    full = call(b, "add_activity", activity_id=a["activity_id"], day=SUN)
    assert full["updated"] is False and full["day_full"]
    flight = call(b, "add_activity", name="Flight home", start=f"{MON}T08:00")["activity_id"]
    with pytest.raises(ToolError, match="pass start"):
        call(b, "add_activity", activity_id=flight, day=SUN)
