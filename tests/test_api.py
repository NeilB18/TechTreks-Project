"""The Django HTTP API: auth, errors, and that trip reads never include budgets."""

import pytest
from conftest import AGENT_TOKEN
from django.test import Client

from trips.services import DjangoBackend

AUTH = {"Authorization": f"Bearer {AGENT_TOKEN}"}


@pytest.fixture
def client(db):
    DjangoBackend().load_seed({
        "trip": {"id": "miami", "name": "Miami", "leader": "aarav"},
        "members": [{"id": "aarav", "name": "Aarav", "handle": "@aarav-venmo"},
                    {"id": "mia", "name": "Mia", "handle": "@mia-venmo"}],
        "budgets": {"mia": {"total": 50000}},
        "expenses": [{"id": "e1", "paid_by": "aarav", "amount": 10000, "description": "Dinner",
                      "category": "FOOD", "split_with": ["aarav", "mia"]}],
    })
    return Client()


def post(client, tool, body, headers=AUTH):
    return client.post(f"/api/tools/{tool}", data=body, content_type="application/json", headers=headers)


def test_requires_token(client):
    assert post(client, "get_balances", {"trip_id": "miami"}, headers={}).status_code == 403
    assert post(client, "get_balances", {"trip_id": "miami"},
                headers={"Authorization": "Bearer wrong"}).status_code == 403
    assert client.get("/api/trips/miami").status_code == 403


def test_tool_call_and_errors(client):
    r = post(client, "get_balances", {"trip_id": "miami"})
    assert r.status_code == 200
    assert r.json()["balances"]["mia"]["owes"][0] == {"to": "aarav", "amount_cents": 5000,
                                                      "handle": "@aarav-venmo"}
    assert post(client, "nope", {}).status_code == 404
    r = post(client, "log_expense", {"trip_id": "miami", "paid_by": "zed", "amount": 100, "currency": "USD",
                                     "description": "x", "category": "FOOD", "split_with": ["mia"]})
    assert r.status_code == 400 and "zed" in r.json()["error"]
    r = post(client, "get_balances", {"trip_id": "miami", "bogus": 1})
    assert r.status_code == 400 and "Bad arguments" in r.json()["error"]
    assert post(client, "convert_currency", {"amount": 10000, "from": "EUR", "to": "USD"}).json()["converted"] == 10800


def test_failed_tool_call_changes_nothing(client):
    post(client, "log_expense", {"trip_id": "miami", "paid_by": "aarav", "amount": 900, "currency": "USD",
                                 "description": "x", "category": "FOOD", "exact_amounts": {"mia": 100}})
    assert len(client.get("/api/trips/miami", headers=AUTH).json()["expenses"]) == 1


def test_trip_reads_never_include_budgets(client):
    for path in ("/api/trips/miami", "/api/trips/miami/summary", "/api/trips/miami/balances"):
        r = client.get(path, headers=AUTH)
        assert r.status_code == 200, path
        assert "50000" not in r.content.decode(), path
        assert "total_cents" not in r.content.decode(), path
    assert client.get("/api/trips/nowhere", headers=AUTH).status_code == 404


def test_expense_and_poll_ids_are_unique_across_trips(db):
    b = DjangoBackend()
    for tid in ("a", "b"):
        b.load_seed({"trip": {"id": tid, "name": tid},
                     "members": [{"id": "x", "name": "X"}, {"id": "y", "name": "Y"}]})
    ids = {b.log_expense(trip_id=t, paid_by="x", amount=100, currency="USD", description="d",
                         category="FOOD", split_with=["x", "y"])["expense_id"] for t in ("a", "b")}
    polls = {b.create_poll(trip_id=t, question="q", options=["1", "2"])["poll_id"] for t in ("a", "b")}
    assert len(ids) == 2 and len(polls) == 2
    b.vote_poll(poll_id=sorted(polls)[1], person_id="x", option="2")
    assert b.close_poll(poll_id=sorted(polls)[1])["winner"] == "2"
