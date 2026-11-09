"""Picking a destination: places checked on the map and against everyone's budget, with flight links (no network).

Runs against the in-memory TripEngine and the Django DjangoBackend.
"""

from urllib.parse import parse_qs, urlparse

import pytest
from conftest import make_backend

from agent.backend.core.engine import TripEngine
from agent.backend.protocol import ToolError, dispatch
from agent.travel.provider import FakeTravel

MEMBERS = [{"id": p, "name": p.title()} for p in ["aarav", "jake", "mia"]]
TRIP = {"id": "t", "start_date": "2027-03-14", "end_date": "2027-03-18"}
BUDGETS = {"aarav": {"total": 120000}, "jake": {"total": 80000}, "mia": {"total": 100000}}
PLACES = [{"name": "Cancún", "est_cost_cents": 60000, "est_flight_cents": 40000},
          {"name": "Miami", "est_cost_cents": 85000, "est_flight_cents": 25000},
          {"name": "Zzqx Imaginary Taco Palace", "est_cost_cents": 30000}]


@pytest.fixture(params=["memory", "django"])
def b(request, db):
    b = make_backend(request.param)
    b.load_seed({"now": "2027-01-10T12:00:00", "trip": {**TRIP, "home_city": "Atlanta"}, "members": MEMBERS,
                 "budgets": BUDGETS})
    return b


def compare(b, places=PLACES):
    return dispatch(b, "compare_destinations", {"trip_id": "t", "places": places})


def test_each_place_shows_who_its_a_stretch_for(b):
    r = compare(b)
    cancun, miami, made_up = r["destinations"]
    assert cancun["fits_everyone"] and cancun["stretch_without_flights"] == []
    assert cancun["stretch_with_flights"] == ["jake"] and cancun["est_total_cents"] == 100000
    assert not miami["fits_everyone"] and miami["stretch_without_flights"] == ["jake"]
    assert miami["stretch_with_flights"] == ["jake", "mia"]
    assert made_up["found_on_map"] is False and made_up["est_flight_cents"] is None
    assert made_up["stretch_with_flights"] == []  # no flight estimate, so no with-flights check
    assert r["from"] == "Atlanta" and r["nights"] == 4 and "vary a lot" in r["note"]


def test_flight_links_start_from_home_on_the_trip_dates(b):
    url = compare(b)["destinations"][0]["flights_url"]
    assert url.startswith("https://www.google.com/travel/flights?q=")
    assert parse_qs(urlparse(url).query)["q"] == ["Flights to Cancún from Atlanta on 2027-03-14 through 2027-03-18"]


def test_home_city_is_needed_first():
    b = TripEngine(travel=FakeTravel())
    b.load_seed({"trip": TRIP, "members": MEMBERS})
    with pytest.raises(ToolError, match="flying from"):
        compare(b)
    dispatch(b, "update_trip", {"trip_id": "t", "changes": {"home_city": " Atlanta "}})
    assert b.summary("t")["trip"]["home_city"] == "Atlanta" and compare(b)["from"] == "Atlanta"


def test_someone_without_a_budget_means_it_doesnt_fit_everyone_yet():
    b = TripEngine(travel=FakeTravel())
    b.load_seed({"trip": {**TRIP, "home_city": "Atlanta"}, "members": MEMBERS,
                 "budgets": {"aarav": {"total": 120000}}})
    r = compare(b, PLACES[:2])
    assert r["no_budget_yet"] == ["jake", "mia"] and not r["destinations"][0]["fits_everyone"]


@pytest.mark.parametrize("places, error", [
    ([PLACES[0]], "2 to 5"),
    ([PLACES[0], {"name": "Miami"}], "est_cost_cents"),
    ([PLACES[0], {"name": "Miami", "est_cost_cents": 1, "est_flight_cents": -5}], "est_flight_cents"),
    ([PLACES[0], {"name": " ", "est_cost_cents": 1}], "name")])
def test_bad_comparisons_are_refused(b, places, error):
    with pytest.raises(ToolError, match=error):
        compare(b, places)


def test_a_map_outage_still_compares():
    class Down(FakeTravel):
        def find_place(self, name, city):
            raise RuntimeError("map is down")
    b = TripEngine(travel=Down())
    b.load_seed({"trip": {**TRIP, "home_city": "Atlanta"}, "members": MEMBERS, "budgets": BUDGETS})
    assert [d["found_on_map"] for d in compare(b, PLACES[:2])["destinations"]] == [None, None]
