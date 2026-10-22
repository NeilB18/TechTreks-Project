"""Google sign-in linking and the private budget API (Google itself isn't called)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from accounts.models import LinkCode
from accounts.services import find_link_command
from bot import groupme, services
from bot.models import GroupChat, PrivateNotice
from trips.models import Person
from trips.services import DjangoBackend

SECRET = "s3cret"


@pytest.fixture
def trip(db, settings, monkeypatch):
    settings.GROUPME_CALLBACK_SECRET = SECRET
    DjangoBackend().load_seed({
        "trip": {"id": "miami", "name": "Miami", "leader": "aarav"},
        "members": [{"id": "aarav", "name": "Aarav", "chat_user_id": "111"},
                    {"id": "mia", "name": "Mia", "chat_user_id": "222"}],
        "budgets": {"mia": {"total": 50000}, "aarav": {"total": 120000}},
        "expenses": [{"id": "e1", "paid_by": "aarav", "amount": 12000, "description": "Dinner",
                      "category": "FOOD", "split_with": ["aarav", "mia"]}],
    })
    GroupChat.objects.create(group_id="g1", bot_id="bot-1", trip_id="miami")
    posts = []
    monkeypatch.setattr(groupme.requests, "post", lambda url, **kw: posts.append(kw["json"]) or _Ok())
    monkeypatch.setattr(services, "make_agent", lambda *a: pytest.fail("link commands must not reach the agent"))
    return posts


class _Ok:
    def raise_for_status(self):
        pass


def signed_in(email="mia@nyu.edu"):
    user = get_user_model().objects.create_user(username=email, email=email)
    client = Client()
    client.force_login(user)
    return client, user


def post_in_group(text, user_id="222", msg_id="m1"):
    return Client().post(f"/groupme/callback/{SECRET}", content_type="application/json", data={
        "id": msg_id, "group_id": "g1", "user_id": user_id, "name": "Mia", "text": text,
        "sender_type": "user"})


def test_link_flow_then_only_your_own_budget(trip):
    client, user = signed_in()
    assert client.get("/api/me/").json() == {"signed_in": True, "email": "mia@nyu.edu", "people": []}
    code = client.post("/api/me/link-code").json()["code"]
    assert client.get("/api/me/trips/miami/budget").status_code == 403

    assert post_in_group(f"@tripbot link {code.lower()}").json()["outcome"] == "linked account"
    assert "linked" in trip[-1]["text"] and "$" not in trip[-1]["text"]
    assert Person.objects.get(person_id="mia").user == user

    PrivateNotice.objects.create(trip_id="miami", person_id="mia", text="Heads up: food budget almost used")
    r = client.get("/api/me/trips/miami/budget").json()
    assert r["person_id"] == "mia"
    assert r["budget"]["total_cents"] == 50000 and r["budget"]["spent_cents"] == 6000
    assert r["notices"][0]["text"] == "Heads up: food budget almost used"
    assert "120000" not in str(r)  # never anyone else's budget
    assert client.get("/api/me/").json()["people"] == [
        {"trip_id": "miami", "trip_name": "Miami", "person_id": "mia", "name": "Mia"}]


def test_link_survives_later_tool_calls(trip):
    client, user = signed_in()
    code = client.post("/api/me/link-code").json()["code"]
    post_in_group(f"@tripbot link {code}")
    DjangoBackend().log_expense(trip_id="miami", paid_by="mia", amount=100, currency="USD",
                                description="x", category="FOOD", split_with=["mia"])
    assert Person.objects.get(person_id="mia").user == user


def test_codes_are_single_use_and_expire(trip):
    client, _ = signed_in()
    code = client.post("/api/me/link-code").json()["code"]
    post_in_group(f"@tripbot link {code}")
    post_in_group(f"@tripbot link {code}", user_id="111", msg_id="m2")
    assert "didn't work" in trip[-1]["text"]
    assert Person.objects.get(person_id="aarav").user is None

    other, _ = signed_in("x@nyu.edu")
    old = other.post("/api/me/link-code").json()["code"]
    LinkCode.objects.filter(code=old).update(expires_at=timezone.now() - timedelta(minutes=1))
    post_in_group(f"@tripbot link {old}", user_id="111", msg_id="m3")
    assert "didn't work" in trip[-1]["text"]


def test_anonymous_and_method_checks(trip):
    anon = Client()
    assert anon.get("/api/me/").json()["signed_in"] is False
    assert anon.post("/api/me/link-code").status_code == 401
    assert anon.get("/api/me/trips/miami/budget").status_code == 401
    client, _ = signed_in()
    assert client.get("/api/me/link-code").status_code == 405


def test_link_code_post_needs_csrf_from_browsers(trip):
    _, user = signed_in()
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(user)
    assert browser.post("/api/me/link-code").status_code == 403
    browser.get("/api/me/")
    token = browser.cookies["csrftoken"].value
    assert browser.post("/api/me/link-code", headers={"X-CSRFToken": token}).status_code == 200


def test_find_link_command():
    assert find_link_command("@tripbot link ab3dE9") == "AB3DE9"
    assert find_link_command("@tripbot can you link the airbnb") is None


def test_google_login_route_exists(db):
    assert Client().get("/accounts/google/login/").status_code in (200, 302)
