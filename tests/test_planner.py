"""Itinerary drafts from the agent's suggested stops: the day layout and the map check (no network)."""

from datetime import date, timedelta

import pytest

from agent.backend.core.engine import ESTIMATES_NOTE, TripEngine
from agent.travel import osm
from agent.travel.planner import is_open, plan_days
from agent.travel.provider import FakeTravel

MON = date(2027, 3, 15)
DAYS = ["2027-03-15", "2027-03-16"]  # the test trip


def week(n):
    return [MON + timedelta(days=i) for i in range(n)]


def stop(name, kind, lat=None, lon=None, hours=None):
    return {"name": name, "kind": kind, "lat": lat, "lon": lon, "hours": hours}


def slots(day):
    return {it["name"]: it["slot"] for it in day["items"]}


def test_each_kind_gets_its_slot_in_time_order():
    [day] = plan_days([stop("Bar", "night"), stop("Cafe", "food"), stop("Museum", "activity"),
                       stop("Grill", "food")], week(1))
    assert [(it["name"], it["slot"]) for it in day["items"]] == [
        ("Museum", "morning"), ("Cafe", "lunch"), ("Grill", "dinner"), ("Bar", "night")]


def test_days_stay_in_one_area():
    north = [stop(f"N{i}", "activity", 25.80 + i / 1000, -80.13) for i in range(2)]
    south = [stop(f"S{i}", "activity", 25.70 + i / 1000, -80.25) for i in range(2)]
    food = [stop("N food", "food", 25.801, -80.13), stop("S food", "food", 25.701, -80.25)]
    days = plan_days([north[0], south[0], north[1], south[1], *food], week(2))
    by_day = [set(slots(d)) for d in days]
    assert {"N0", "N1", "N food"} in by_day and {"S0", "S1", "S food"} in by_day


def test_food_spreads_across_days_when_there_are_no_coordinates():
    days = plan_days([stop(f"Food {i}", "food") for i in range(3)], week(3))
    assert [len(d["items"]) for d in days] == [1, 1, 1]


def test_a_stop_moves_to_a_slot_its_open_for():
    dinner_only = {d: [(1080, 1380)] for d in range(7)}  # 18:00-23:00
    [day] = plan_days([stop("Steakhouse", "food", hours=dinner_only)], week(1))
    assert day["items"][0]["slot"] == "dinner" and not day["items"][0]["hours_conflict"]


def test_a_stop_closed_on_its_day_moves_to_a_day_its_open():
    closed_mondays = {d: [(600, 1320)] for d in range(1, 7)}
    mon, tue = plan_days([stop("Museum", "activity", hours=closed_mondays)], week(2))
    assert mon["items"] == [] and not tue["items"][0]["hours_conflict"]


def test_meals_spread_across_days_before_staying_close():
    acts = [stop("North", "activity", 25.80, -80.13), stop("South", "activity", 25.70, -80.25)]
    food = [stop("N lunch", "food", 25.801, -80.13), stop("N dinner", "food", 25.802, -80.13)]
    days = plan_days([*acts, *food], week(2))
    assert [sum(it["kind"] == "food" for it in d["items"]) for d in days] == [1, 1]


def test_closed_all_day_is_flagged():
    closed_mondays = {d: [(600, 1320)] for d in range(1, 7)}
    [day] = plan_days([stop("Museum", "activity", hours=closed_mondays)], week(1))
    assert day["items"][0]["hours_conflict"]


def test_is_open_counts_last_nights_late_hours():
    late = {4: [(1080, 1560)]}  # Friday 18:00 to Saturday 02:00
    assert is_open(late, 5, 30, 90) is True       # Saturday 00:30-01:30
    assert is_open(late, 5, 120, 180) is False    # Saturday 02:00-03:00
    assert is_open(None, 0, 0, 60) is None


def test_short_address_drops_the_name_and_joins_the_house_number():
    p = osm.Place("Versailles Restaurant", 0, 0, "", "Versailles Restaurant, 3555, Southwest 8th Street, "
                  "Little Havana, Miami, Florida, United States")
    assert osm.short_address(p) == "3555 Southwest 8th Street, Little Havana"


# ------------------------------------------------------------------ the tool
class StubTravel(FakeTravel):
    def __init__(self, places=None, fail=()):
        self.places, self.fail, self.calls = places or {}, set(fail), []

    def find_place(self, name, city):
        self.calls.append(name)
        if name in self.fail:
            raise RuntimeError("map is down")
        return self.places.get(name) or super().find_place(name, city)


def engine(travel, start="2027-03-15", end="2027-03-16"):
    b = TripEngine(travel=travel)
    b.load_seed({"trip": {"id": "t", "destination": "Miami", "start_date": start, "end_date": end},
                 "members": [{"id": "a", "name": "A"}]})
    return b


def test_draft_has_links_estimates_and_credit():
    d = engine(FakeTravel()).generate_itinerary("t", days=DAYS, places=[
        {"name": "Versailles Restaurant", "kind": "food", "est_cost_cents": 2500},
        {"name": "Zzqx Imaginary Taco Palace", "kind": "food"}])
    items = [it for day in d["days"] for it in day["items"]]
    found = next(it for it in items if it["name"] == "Versailles Restaurant")
    missing = next(it for it in items if it["name"] == "Zzqx Imaginary Taco Palace")
    assert found["verified"] and found["start"].endswith("T12:30") and found["est_cost_cents"] == 2500
    assert found["maps_url"].startswith("https://www.google.com/maps/search/")
    assert missing["verified"] is False and missing["lat"] is None and missing["maps_url"]
    assert d["not_found"] == ["Zzqx Imaginary Taco Palace"] and d["map_check_failed"] == []
    assert d["note"] == ESTIMATES_NOTE and d["credit"] == "© OpenStreetMap contributors"


def test_lookups_are_capped_per_day():
    travel = StubTravel()
    d = engine(travel).generate_itinerary("t", days=DAYS, places=[{"name": f"Spot {i}", "kind": "activity"} for i in range(8)])
    assert len(travel.calls) == 6 and d["skipped"] == ["Spot 6", "Spot 7"]
    assert sum(len(day["items"]) for day in d["days"]) == 6


def test_a_map_outage_keeps_the_draft_going():
    d = engine(StubTravel(fail={"Wynwood Walls"})).generate_itinerary(
        "t", days=DAYS, places=[{"name": "Wynwood Walls", "kind": "activity"}, {"name": "Versailles Restaurant", "kind": "food"}])
    assert d["map_check_failed"] == ["Wynwood Walls"] and d["not_found"] == []
    items = {it["name"]: it for day in d["days"] for it in day["items"]}
    assert items["Wynwood Walls"]["verified"] is None and items["Versailles Restaurant"]["verified"] is True


def test_real_hours_from_the_map_move_a_stop():
    hours = "Mo-Su 17:00-23:00"
    steak = osm.Place("Steakhouse", 25.77, -80.19, "amenity/restaurant", "Steakhouse, Miami",
                      opening_hours=hours, hours=osm.parse_opening_hours(hours))
    d = engine(StubTravel({"Steakhouse": steak}), end="2027-03-15").generate_itinerary(
        "t", days=["2027-03-15"], places=[{"name": "Steakhouse", "kind": "food"}])
    [item] = d["days"][0]["items"]
    assert item["slot"] == "dinner" and item["opening_hours"] == hours and not item["hours_conflict"]


def test_saved_activities_keep_the_map_check():
    b = engine(FakeTravel())
    d = b.generate_itinerary("t", days=DAYS, places=[{"name": "Wynwood Walls", "kind": "activity"}])
    b.generate_itinerary("t", save_draft_id=d["draft_id"])
    [a] = b.get_trip("t")["activities"]
    assert a["verified"] is True and a["lat"] is not None and a["start"] == "2027-03-15T10:00"
    assert a["maps_url"].startswith("https://www.google.com/maps/search/")


def test_a_new_draft_replaces_the_old_one():
    b = engine(FakeTravel())
    old = b.generate_itinerary("t", days=DAYS, places=[{"name": "Wynwood Walls", "kind": "activity"}])
    new = b.generate_itinerary("t", days=DAYS, places=[{"name": "Vizcaya Museum", "kind": "activity"}])
    assert new["replaced_drafts"] == [old["draft_id"]] and b.get_trip("t")["itinerary_drafts"] == [new["draft_id"]]
    with pytest.raises(Exception, match="No draft"):
        b.generate_itinerary("t", save_draft_id=old["draft_id"])


def test_a_draft_leaves_out_places_already_on_the_trip():
    b = engine(FakeTravel())
    places = [{"name": "Wynwood Walls", "kind": "activity"}, {"name": "Versailles Restaurant", "kind": "food"}]
    b.generate_itinerary("t", save_draft_id=b.generate_itinerary("t", days=DAYS, places=places)["draft_id"])
    again = b.generate_itinerary("t", days=DAYS, places=places)
    assert again["already_on_trip"] == ["Versailles Restaurant", "Wynwood Walls"]
    assert all(day["items"] == [] for day in again["days"])


def test_saving_skips_a_stop_added_since_the_draft():
    b = engine(FakeTravel())
    d = b.generate_itinerary("t", days=DAYS, places=[{"name": "Wynwood Walls", "kind": "activity"}])
    b.add_activity("t", name="Wynwood Walls", start=d["days"][0]["items"][0]["start"])
    saved = b.generate_itinerary("t", save_draft_id=d["draft_id"])
    assert saved["activity_ids"] == [] and saved["already_on_trip"] == ["Wynwood Walls"]
    assert len(b.get_trip("t")["activities"]) == 1


def test_the_same_place_twice_is_looked_up_once():
    travel = StubTravel()
    d = engine(travel).generate_itinerary("t", days=DAYS, places=[{"name": "Wynwood Walls", "kind": "activity"},
                                                       {"name": "wynwood walls ", "kind": "activity"}])
    assert travel.calls == ["Wynwood Walls"] and sum(len(day["items"]) for day in d["days"]) == 1


@pytest.mark.parametrize("bad, error", [
    ([{"name": "", "kind": "food"}], "name and a kind"), ([{"name": "X"}], "name and a kind"),
    (["Versailles"], "name and a kind"), ([{"name": "X", "kind": "food", "est_cost_cents": "25"}], "whole cents"),
    ([{"name": "X", "kind": "food", "est_cost_cents": -100}], "whole cents")])
def test_bad_places_are_rejected_before_any_lookup(bad, error):
    travel = StubTravel()
    with pytest.raises(Exception, match=error):
        engine(travel).generate_itinerary("t", days=DAYS, places=bad)
    assert travel.calls == []
