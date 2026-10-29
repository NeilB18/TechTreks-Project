from io import StringIO

import pytest
from django.core.management import call_command

from trips.models import Trip
from trips.services import DjangoBackend


@pytest.mark.django_db
def test_demo_trip_is_persisted_and_reruns_preserve_changes():
    out = StringIO()
    call_command("seed_demo_trip", trip_id="sample-trip", stdout=out)
    backend = DjangoBackend()
    detail = backend.get_trip(trip_id="sample-trip")
    assert len(detail["members"]) == 6
    assert len(detail["activities"]) == 11
    assert len(detail["expenses"]) == 6
    assert sum(backend.get_balances(trip_id="sample-trip")["net_balances"].values()) == 0
    assert "total_cents" not in str(detail)

    Trip.objects.filter(pk="sample-trip").update(name="Keep my changes")
    call_command("seed_demo_trip", trip_id="sample-trip", stdout=out)
    assert Trip.objects.get(pk="sample-trip").name == "Keep my changes"
    assert "left unchanged" in out.getvalue()
