"""0010_planning_cut carries real trips over: lodging becomes its saved name, ideas lose their map details, and
"itinerary_saves" leaves leader_approval."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("trips", "0009_trip_theme")]
AFTER = [("trips", "0010_planning_cut")]


@pytest.mark.django_db(transaction=True)
def test_planning_cut_keeps_what_the_group_wrote():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    old = executor.loader.project_state(BEFORE).apps
    Trip, Activity = old.get_model("trips", "Trip"), old.get_model("trips", "Activity")
    trip = Trip.objects.create(
        id="miami", name="Miami", share_token="abcdefghjkmn", home_city="Atlanta", planning_notes="chill",
        leader_approval=["trip_changes", "itinerary_saves"],
        lodging={"name": "Freehand Miami", "address": "2727 Indian Creek Dr", "lat": 25.8, "lon": -80.1,
                 "maps_url": "https://www.google.com/maps/search/?api=1&query=Freehand"},
        ideas=[{"idea_id": "i1", "name": "Wynwood Walls", "kind": "activity", "verified": True, "lat": 25.8,
                "lon": -80.2, "maps_url": "x", "est_cost_cents": 0, "suggested_by": "mia"}])
    Activity.objects.create(trip=trip, activity_id="a1", name="Versailles", start="2027-03-15T12:30",
                            end="2027-03-15T14:00", kind="food", verified=True, lat=25.7, lon=-80.3)
    Trip.objects.create(id="empty", name="Empty", share_token="nmkjhgfedcba")

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(AFTER)
    new = executor.loader.project_state(AFTER).apps
    Trip, Activity = new.get_model("trips", "Trip"), new.get_model("trips", "Activity")
    trip = Trip.objects.get(id="miami")
    assert trip.lodging == "Freehand Miami"
    assert trip.ideas == [{"idea_id": "i1", "name": "Wynwood Walls", "est_cost_cents": 0, "suggested_by": "mia"}]
    assert trip.leader_approval == ["trip_changes"]
    assert Trip.objects.get(id="empty").lodging is None
    a = Activity.objects.get(activity_id="a1")
    assert (a.start, a.end, a.slot) == ("2027-03-15T12:30", "2027-03-15T14:00", None)  # saved times stay
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())  # leave the database migrated for other tests
