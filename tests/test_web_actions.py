"""The trip page's two actions for members: mark a payment as sent, and change your own budget.
Each saves through the same tools as the bot, then the bot posts one short line in the group."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client

from bot import groupme
from bot.models import GroupChat
from trips.models import Budget, Expense, Person
from trips.services import DjangoBackend


class _Ok:
    def raise_for_status(self):
        pass


@pytest.fixture
def mia(db, monkeypatch):
    cache.clear()
    DjangoBackend().load_seed({
        "trip": {"id": "miami", "name": "Miami"},
        "members": [{"id": "aarav", "name": "Aarav", "handle": "@aarav-venmo"}, {"id": "mia", "name": "Mia"}],
        "budgets": {"mia": {"total": 50000, "limits": {"DRINKS": 10000}}},
        "expenses": [{"id": "e1", "paid_by": "aarav", "amount": 12000, "description": "Dinner",
                      "category": "FOOD", "split_with": ["aarav", "mia"]}],  # Mia owes Aarav $60
    })
    GroupChat.objects.create(group_id="g1", bot_id="bot-1", trip_id="miami")
    posts = []
    monkeypatch.setattr(groupme.requests, "post", lambda url, **kw: posts.append(kw["json"]["text"]) or _Ok())
    user = get_user_model().objects.create_user(username="mia@x.edu", email="mia@x.edu")
    Person.objects.filter(trip_id="miami", person_id="mia").update(user=user)
    client = Client()
    client.force_login(user)
    client.posts = posts
    return client


def post(client, path, body):
    return client.post(f"/api/me/trips/miami/{path}", data=json.dumps(body), content_type="application/json")


def paybacks():
    return Expense.objects.filter(trip_id="miami", category="SETTLEMENT").count()


def test_mark_as_sent_records_once_and_posts_a_short_line(mia):
    pay = {"to": "aarav", "amount_cents": 2500, "request_id": "r1"}
    assert post(Client(), "payments", pay).status_code == 401
    for bad in ({**pay, "request_id": ""}, {**pay, "amount_cents": 0}, {**pay, "amount_cents": "25"},
                {**pay, "to": "mia"}, {**pay, "to": "zed"}):
        assert post(mia, "payments", bad).status_code == 400, bad
    over = post(mia, "payments", {**pay, "amount_cents": 7000})
    assert over.status_code == 400 and over.json()["owed_cents"] == 6000

    # Partial is fine. A double tap (same request_id) records it once.
    assert post(mia, "payments", pay).status_code == 200
    assert post(mia, "payments", pay).status_code == 200
    assert paybacks() == 1 and mia.posts == ["Mia sent Aarav $25."]
    assert DjangoBackend().get_balances(trip_id="miami")["net_balances"] == {"aarav": 3500, "mia": -3500}

    assert post(mia, "payments", {**pay, "amount_cents": 3500, "request_id": "r2"}).status_code == 200
    assert mia.posts[-1] == "Mia sent Aarav $35." and paybacks() == 2
    # Nothing left to send.
    assert post(mia, "payments", {**pay, "amount_cents": 1, "request_id": "r3"}).status_code == 400


def test_only_the_payer_marks_it(mia):
    # Aarav is owed, not paying: he has no payment to Mia to mark.
    aarav = get_user_model().objects.create_user(username="aarav", email="a@x.edu")
    Person.objects.filter(trip_id="miami", person_id="aarav").update(user=aarav)
    client = Client()
    client.force_login(aarav)
    assert post(client, "payments", {"to": "mia", "amount_cents": 100, "request_id": "x"}).status_code == 400
    assert paybacks() == 0


def test_change_my_budget_keeps_limits_and_posts_once(mia):
    r = post(mia, "budget", {"total_cents": 60000})
    assert r.status_code == 200 and r.json()["budget"]["total_cents"] == 60000
    budget = Budget.objects.get(person__trip_id="miami", person__person_id="mia")
    assert budget.limits == {"DRINKS": 10000}
    assert mia.posts == ["Mia's budget is now $600."]
    post(mia, "budget", {"total_cents": 60000})  # no change, no post
    assert mia.posts == ["Mia's budget is now $600."]
    for bad in (0, -5, "600", None, 10**12):
        assert post(mia, "budget", {"total_cents": bad}).status_code == 400
    assert mia.get("/api/me/trips/miami/budget").json()["budget"]["total_cents"] == 60000


def test_saves_even_when_the_group_post_fails_or_there_is_no_group(mia, monkeypatch):
    def boom(url, **kw):
        raise RuntimeError("GroupMe down")
    monkeypatch.setattr(groupme.requests, "post", boom)
    assert post(mia, "budget", {"total_cents": 70000}).status_code == 200
    GroupChat.objects.all().delete()
    assert post(mia, "payments", {"to": "aarav", "amount_cents": 6000, "request_id": "r9"}).status_code == 200
    assert paybacks() == 1
