"""Romir's budget-warning rules (agent/backend/fake/rules.py) and how tools report them."""

import pytest
from conftest import make_backend

from agent.backend.fake import rules
from agent.backend.protocol import dispatch


def flags(total, spent, planned=0, progress=None, limits=None, spent_cat="FOOD", upcoming=()):
    return rules.budget_flags(total, limits or {}, {spent_cat: spent}, {"ACTIVITIES": planned} if planned else {},
                              progress, list(upcoming))


def test_checkpoints_at_50_80_100():
    assert set(flags(10000, 4900)) == set()
    assert set(flags(10000, 5000)) == {"total_50"}
    assert set(flags(10000, 8000)) == {"total_50", "total_80"}
    assert set(flags(10000, 10000)) == {"total_50", "total_80", "total_100"}
    assert flags(10000, 12000)["total_100"] == "You're $20 over your $100 budget ($120 spent)."


def test_over_budget_message_suggests_upcoming_plans():
    f = flags(50000, 52000, upcoming=[("Boat tour", 12000), ("Jet ski", 9000)])
    assert f["total_100"].endswith("Coming up: Boat tour ~$120, Jet ski ~$90.")


def test_planned_wont_fit():
    f = flags(50000, 30000, planned=21300, upcoming=[("Boat tour", 13300), ("Club night", 8000)])
    assert f["planned_over"] == ("Your upcoming plans (Boat tour ~$133, Club night ~$80) "
                                 "would put you $13 over your $500 budget.")
    assert "planned_over" not in flags(50000, 52000, planned=1000)  # already over: total_100 covers it


def test_pace_only_during_the_trip_and_after_20_percent():
    assert "pace" in flags(70000, 42000, progress=(2, 5))  # 60% used, 40% of the trip done
    assert "pace" not in flags(70000, 38000, progress=(2, 5))  # 54%: only 14 points ahead
    assert "pace" not in flags(70000, 42000, progress=None)  # before/after the trip
    assert "pace" not in flags(10000, 1900, progress=(1, 10))  # under 20% used
    assert rules.trip_progress("2027-03-14", "2027-03-18", "2027-03-15T20:00") == (2, 5)
    assert rules.trip_progress("2027-03-14", "2027-03-18", "2027-03-13T20:00") is None


def test_category_limits_at_90_and_over():
    limits = {"DRINKS": 10000}
    assert "cat_DRINKS_90" in flags(100000, 9000, limits=limits, spent_cat="DRINKS")
    over = flags(100000, 10500, limits=limits, spent_cat="DRINKS")
    assert "cat_DRINKS_90" not in over and over["cat_DRINKS_100"] == "Drinks: $5 over your $100 limit (including plans)."


def test_only_newly_crossed_lines_and_highest_checkpoint():
    before = flags(10000, 4000)
    after = flags(10000, 9000)  # jumps past 50% and 80% at once
    assert rules.newly_crossed(before, after) == ["You've used 90% of your budget ($90 of $100)."]
    assert rules.newly_crossed(after, flags(10000, 9500)) == []  # nothing new: no repeat warning


@pytest.fixture(params=["fake", "django"])
def trip(request, db):
    b = make_backend(request.param)
    b.load_seed({
        "now": "2027-03-15T20:00:00",
        "trip": {"id": "t", "status": "ACTIVE", "start_date": "2027-03-14", "end_date": "2027-03-18"},
        "members": [{"id": p, "name": p.title(), "handle": f"@{p}-venmo"} for p in ["aarav", "jake", "mia"]],
        "budgets": {"jake": {"total": 70000}},
        "expenses": [{"id": "e1", "paid_by": "aarav", "amount": 90000, "description": "Airbnb",
                      "category": "LODGING", "split_with": ["aarav", "jake", "mia"]}],
    })
    return b


def test_expense_that_crosses_lines_warns_once(trip):
    args = {"trip_id": "t", "paid_by": "aarav", "currency": "USD", "category": "ACTIVITIES",
            "split_with": ["aarav", "jake", "mia"]}
    r = dispatch(trip, "log_expense", {**args, "amount": 36000, "description": "Boat tour"})  # Jake: $300 -> $420
    assert sorted(r["budget_warnings"]["jake"]) == [
        "You've used 60% of your budget ($420 of $700).",
        "You've used 60% of your budget and it's only day 2 of 5. That leaves about $93.33 a day for the rest of the trip.",
    ]
    r = dispatch(trip, "log_expense", {**args, "amount": 3000, "description": "Snacks"})  # still 61%
    assert r["budget_warnings"] == {}
    status = trip.get_budget_status("t", "jake")
    assert len(status["warnings"]) == 2 and status["over_by_cents"] == 0
