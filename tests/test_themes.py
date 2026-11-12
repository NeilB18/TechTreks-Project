"""Trip page themes: the bot picks one with the destination; once a member picks one on the page, it stays."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from agent.backend.core.engine import TripEngine
from agent.backend.protocol import ToolError
from conftest import AGENT_TOKEN
from trips.models import Person, Trip
from trips.services import DjangoBackend

SEED = {"trip": {"id": "miami", "name": "Miami"},
        "members": [{"id": "aarav", "name": "Aarav"}, {"id": "mia", "name": "Mia"}]}


def test_bot_sets_the_theme_until_a_member_picks_one():
    e = TripEngine()
    e.load_seed(SEED)
    e.update_trip("miami", {"destination": "Miami", "theme": "sunset"})
    assert e.summary("miami")["trip"]["theme"] == "sunset"
    with pytest.raises(ToolError, match="theme must be one of"):
        e.update_trip("miami", {"theme": "neon"})

    e.set_theme("miami", "campfire")  # a member, on the page
    out = e.update_trip("miami", {"destination": "Miami Beach", "theme": "night_swim"})
    assert e.summary("miami")["trip"]["theme"] == "campfire"
    assert "stays" in out["theme_kept"]
    assert e.summary("miami")["trip"]["destination"] == "Miami Beach"  # the rest of the change still saved


@pytest.fixture
def member(db):
    DjangoBackend().load_seed(SEED)
    user = get_user_model().objects.create_user(username="mia@x.edu", email="mia@x.edu")
    Person.objects.filter(trip_id="miami", person_id="mia").update(user=user)
    client = Client()
    client.force_login(user)
    return client


def post_theme(client, theme, trip="miami"):
    return client.post(f"/api/me/trips/{trip}/theme", data=json.dumps({"theme": theme}),
                       content_type="application/json")


def test_members_pick_the_theme_on_the_page(member):
    assert post_theme(Client(), "campfire").status_code == 401
    outsider = Client()
    outsider.force_login(get_user_model().objects.create_user(username="zed", email="zed@x.edu"))
    assert post_theme(outsider, "campfire").status_code == 403
    assert post_theme(member, "neon").status_code == 400

    assert post_theme(member, "campfire").json() == {"theme": "campfire"}
    row = Trip.objects.get(id="miami")
    assert (row.theme, row.theme_set_by) == ("campfire", "member")
    # The bot's pick no longer changes it, and anyone with the link sees it.
    DjangoBackend().update_trip(trip_id="miami", changes={"theme": "sunset"})
    shared = Client().get(f"/api/share/{row.share_token}", headers={"Authorization": f"Bearer {AGENT_TOKEN}"})
    assert shared.json()["trip"]["theme"] == "campfire"
