"""Where the group is staying: saved as the group wrote it, with no lookup.

Runs against the in-memory TripEngine and the Django DjangoBackend.
"""

import pytest
from conftest import make_backend

from agent.backend.core.engine import MAX_LODGING, TripEngine
from agent.backend.protocol import ToolError, dispatch

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


def test_lodging_is_saved_as_written(b):
    assert stay(b, "  Freehand Miami ")["updated"]
    assert lodging(b) == "Freehand Miami"


def test_a_correction_replaces_it_and_empty_clears_it(b):
    stay(b, "Freehand Miami")
    stay(b, "2727 Indian Creek Dr")
    assert lodging(b) == "2727 Indian Creek Dr"
    stay(b, "")
    assert lodging(b) is None


def test_lodging_doesnt_need_a_destination():
    b = TripEngine()
    b.load_seed({"trip": {**TRIP, "destination": None}, "members": MEMBERS})
    stay(b, "Freehand Miami")
    assert lodging(b) == "Freehand Miami"


def test_lodging_is_text_of_a_sensible_length(b):
    with pytest.raises(ToolError, match="hotel name or address"):
        stay(b, "x" * (MAX_LODGING + 1))
    with pytest.raises(ToolError, match="hotel name or address"):
        stay(b, {"name": "Freehand"})


def test_a_seed_can_set_lodging():
    b = TripEngine()
    b.load_seed({"trip": {**TRIP, "lodging": "Freehand Miami"}, "members": MEMBERS})
    assert lodging(b) == "Freehand Miami"
