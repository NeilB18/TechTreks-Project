"""Deterministic tests for the backend data rules (no model calls).

Each test runs against the in-memory FakeBackend and the Django DjangoBackend.
"""

import pytest
from conftest import make_backend

from agent.backend.fake import rules
from agent.backend.protocol import ToolError, dispatch

MEMBERS = [{"id": p, "name": p.title(), "handle": f"@{p}-venmo"} for p in ["aarav", "jake", "mia"]]


@pytest.fixture(params=["fake", "django"])
def b(request, db):
    b = make_backend(request.param)
    b.load_seed({"now": "2027-03-01T12:00:00",
                 "trip": {"id": "t", "leader": "aarav", "start_date": "2027-03-14",
                          "end_date": "2027-03-18", "destination": "Miami"},
                 "members": MEMBERS})
    return b


def log(b, **kw):
    args = {"trip_id": "t", "paid_by": "aarav", "amount": 10000, "currency": "USD",
            "description": "x", "category": "FOOD"} | kw
    return dispatch(b, "log_expense", args)


def test_equal_split_leftover_cent_goes_in_id_order(b):
    r = log(b, amount=10000, split_with=["mia", "jake", "aarav"])
    assert r["shares"] == {"aarav": 3334, "jake": 3333, "mia": 3333}
    # Net changes: Aarav paid $100 and owes $33.34 of it.
    assert r["splits"] == {"aarav": 6666, "jake": -3333, "mia": -3333}
    assert sum(r["splits"].values()) == 0


def test_percentage_split_is_per_expense(b):
    r = log(b, amount=100000, percentages={"aarav": 40, "jake": 30, "mia": 30})
    assert r["shares"] == {"aarav": 40000, "jake": 30000, "mia": 30000}
    with pytest.raises(ToolError):
        log(b, amount=100000, percentages={"aarav": 50, "jake": 30})
    with pytest.raises(ToolError):
        log(b, split_with=["aarav"], percentages={"aarav": 100})


def test_exact_amounts_must_sum(b):
    with pytest.raises(ToolError):
        log(b, amount=9000, exact_amounts={"aarav": 4000, "mia": 3000})


def test_split_with_and_exact_are_exclusive(b):
    with pytest.raises(ToolError):
        log(b, split_with=["aarav"], exact_amounts={"aarav": 10000})


def test_opt_out_auto_excluded_and_override(b):
    dispatch(b, "set_exclusion", {"trip_id": "t", "person_id": "jake", "category": "DRINKS"})
    r = log(b, category="DRINKS", amount=6000, split_with=["aarav", "jake", "mia"])
    assert r["shares"] == {"aarav": 3000, "mia": 3000}
    assert r["auto_excluded"][0]["person_id"] == "jake"
    r = log(b, category="DRINKS", amount=6000, split_with=["aarav", "jake", "mia"], override_opt_outs=["jake"])
    assert r["shares"]["jake"] == 2000


def test_payer_outside_split_is_owed_everything(b):
    r = log(b, paid_by="jake", amount=35000, split_with=["aarav", "mia"])
    assert r["shares"] == {"aarav": 17500, "mia": 17500}  # Jake paid but isn't in the split
    bal = b.get_balances("t")
    assert bal["net_balances"] == {"jake": 35000, "aarav": -17500, "mia": -17500}
    assert bal["suggested_payments"] == [
        {"from": "aarav", "to": "jake", "amount_cents": 17500, "handle": "@jake-venmo"},
        {"from": "mia", "to": "jake", "amount_cents": 17500, "handle": "@jake-venmo"}]
    assert b.get_budget_status("t", "jake")["spent_cents"] == 0


def test_foreign_currency_converted_with_rate(b):
    r = log(b, amount=180000, currency="MXN", split_with=["aarav", "jake", "mia"])
    assert r["base_amount"] == round(180000 * 0.0556)
    assert r["fx_rate"] == 0.0556
    assert sum(r["shares"].values()) == r["base_amount"]
    assert sum(r["splits"].values()) == 0


def test_refund_same_ratio_and_netted_settle_up(b):
    # Example 9: Jake already paid Aarav back, then half the tickets are refunded.
    e = log(b, amount=30000, split_with=["aarav", "jake", "mia"])["expense_id"]
    dispatch(b, "record_payback", {"trip_id": "t", "from_person": "jake", "to_person": "aarav",
                                   "amount": 10000, "currency": "USD"})
    r = dispatch(b, "record_refund", {"expense_id": e, "amount": 15000, "currency": "USD"})
    assert r["per_person"] == {"aarav": 5000, "jake": 5000, "mia": 5000}
    assert b.get_balances("t")["net_balances"] == {"jake": 5000, "mia": -5000}
    # Netted across the group: Mia pays Jake directly; Aarav is square.
    assert b.settle_up(b.trips["t"]) == {("mia", "jake"): 5000}


def test_payback_lowers_debt_and_is_validated(b):
    log(b, amount=9000, split_with=["aarav", "jake", "mia"])
    r = dispatch(b, "record_payback", {"trip_id": "t", "from_person": "jake", "to_person": "aarav",
                                       "amount": 3000, "currency": "USD"})
    assert r["base_amount"] == 3000
    assert b.settle_up(b.trips["t"]) == {("mia", "aarav"): 3000}
    expense = b.get_trip("t")["expenses"][-1]
    assert expense["category"] == "SETTLEMENT" and expense["shares"] == {"aarav": 3000}
    for bad in [{"to_person": "jake"}, {"amount": 0}, {"to_person": "zed"}]:
        with pytest.raises(ToolError):
            dispatch(b, "record_payback", {"trip_id": "t", "from_person": "jake", "to_person": "aarav",
                                           "amount": 3000, "currency": "USD"} | bad)
    with pytest.raises(ToolError):
        log(b, category="SETTLEMENT", exact_amounts={"jake": 10000})


def test_refund_cannot_exceed_expense(b):
    e = log(b, amount=10000, split_with=["aarav", "jake"])["expense_id"]
    with pytest.raises(ToolError):
        dispatch(b, "record_refund", {"expense_id": e, "amount": 10001, "currency": "USD"})


def test_dropout_keeps_past_splits_and_leaves_activities(b):
    log(b, amount=120000, split_with=["aarav", "jake", "mia"])
    dispatch(b, "add_activity", {"trip_id": "t", "name": "Boat", "est_cost_cents": 30000,
                                 "cost_is_per_person": False, "start": "2027-03-15"})
    r = dispatch(b, "remove_member", {"trip_id": "t", "person_id": "mia"})
    assert r["removed_from_activities"] == ["a1"]
    assert b.settle_up(b.trips["t"])[("mia", "aarav")] == 40000
    assert b.summary("t")["activities"][0]["est_per_person_cents"] == 15000
    with pytest.raises(ToolError):
        log(b, split_with=["aarav", "mia"])


def test_budget_counts_share_not_payment_and_skips_settlements(b):
    dispatch(b, "set_budget", {"trip_id": "t", "person_id": "aarav", "total": 50000})
    log(b, paid_by="aarav", amount=30000, split_with=["aarav", "jake", "mia"])
    dispatch(b, "record_payback", {"trip_id": "t", "from_person": "jake", "to_person": "aarav",
                                   "amount": 5000, "currency": "USD"})
    s = b.get_budget_status("t", "aarav")
    assert s["spent_cents"] == 10000 and s["remaining_cents"] == 40000


def test_budget_warning_counts_planned_activities(b):
    # Example 1: a $400 group-total boat tour split 4 ways fits Mia's $140 activities limit;
    # after a dropout it's ~$133 each, leaving under 10% of the limit.
    dispatch(b, "add_member", {"trip_id": "t", "chat_user_id": "priya", "name": "Priya"})
    dispatch(b, "set_budget", {"trip_id": "t", "person_id": "mia", "total": 90000,
                               "limits": {"ACTIVITIES": 14000}})
    dispatch(b, "add_activity", {"trip_id": "t", "name": "Boat", "est_cost_cents": 40000,
                                 "cost_is_per_person": False, "start": "2027-03-15"})
    assert b.get_budget_status("t", "mia")["warnings"] == []
    dispatch(b, "remove_member", {"trip_id": "t", "person_id": "priya"})
    assert b.get_budget_status("t", "mia")["warnings"] == ["ACTIVITIES under 10% remaining"]


def test_budget_warnings_come_from_category_limits_only(b):
    dispatch(b, "set_budget", {"trip_id": "t", "person_id": "jake", "total": 10000})
    log(b, amount=29000, split_with=["aarav", "jake", "mia"])  # Jake's share is nearly his total
    s = b.get_budget_status("t", "jake")
    assert s["remaining_cents"] == 333 and s["warnings"] == []
    dispatch(b, "set_budget", {"trip_id": "t", "person_id": "jake", "total": 10000,
                               "limits": {"FOOD": 9000}})
    assert b.get_budget_status("t", "jake")["warnings"] == ["FOOD over limit by $6.67 including planned activities"]


def test_tier_prices_round_to_dollar():
    assert [rules.tier_price(83333, m) for m in rules.PRESET_MULTIPLIERS] == \
        [41700, 62500, 83300, 104200, 125000, 166700]
    assert rules.tier_price(83333, 1.1) == 91700


def test_travel_tips_never_return_individual_budgets(b):
    for pid, total in [("aarav", 120000), ("jake", 80000), ("mia", 50000)]:
        dispatch(b, "set_budget", {"trip_id": "t", "person_id": pid, "total": total})
    r = dispatch(b, "get_travel_tips", {"trip_id": "t", "destination": "Miami",
                                        "multipliers": [1.1], "prices_only": True})
    assert r["average_cents"] == 83333 and r["tiers"] == [{"multiplier": 1.1, "budget_cents": 91700}]
    assert "120000" not in str(r) and "50000" not in str(r)
    u = dispatch(b, "update_trip", {"trip_id": "t", "changes": {"group_budget": 91700}})
    assert u["members_below_group_budget"] == ["jake", "mia"]


def test_date_change_reports_activities_outside(b):
    dispatch(b, "add_activity", {"trip_id": "t", "name": "Boat", "start": "2027-03-15T10:00"})
    r = dispatch(b, "update_trip", {"trip_id": "t", "changes": {"start_date": "2027-03-16",
                                                               "end_date": "2027-03-20"}})
    assert r["activities_outside_dates"] == ["a1"]


def test_activity_cannot_end_before_it_starts(b):
    with pytest.raises(ToolError):
        dispatch(b, "add_activity", {"trip_id": "t", "name": "Boat", "start": "2027-03-15T12:00",
                                     "end": "2027-03-15T10:00"})
    a = dispatch(b, "add_activity", {"trip_id": "t", "name": "Boat", "start": "2027-03-15T10:00",
                                     "end": "2027-03-15T12:00"})["activity_id"]
    with pytest.raises(ToolError):
        dispatch(b, "add_activity", {"trip_id": "t", "activity_id": a, "end": "2027-03-15T09:00"})


def test_poll_closes_itself_after_closes_at(b):
    p = dispatch(b, "create_poll", {"trip_id": "t", "question": "Where?", "options": ["Miami", "Cancún"],
                                    "closes_at": "2027-03-01T11:00"})["poll_id"]  # "now" is 12:00
    with pytest.raises(ToolError):
        dispatch(b, "vote_poll", {"poll_id": p, "person_id": "aarav", "option": "Miami"})
    assert b.summary("t")["open_polls"] == []
    with pytest.raises(ToolError):
        dispatch(b, "create_poll", {"trip_id": "t", "question": "When?", "options": ["A", "B"],
                                    "closes_at": "Friday"})


def test_poll_flow(b):
    p = dispatch(b, "create_poll", {"trip_id": "t", "question": "Where?", "options": ["Miami", "Cancún"]})["poll_id"]
    dispatch(b, "vote_poll", {"poll_id": p, "person_id": "aarav", "option": "Cancún"})
    dispatch(b, "vote_poll", {"poll_id": p, "person_id": "jake", "option": "Cancún"})
    assert dispatch(b, "close_poll", {"poll_id": p})["winner"] == "Cancún"
    with pytest.raises(ToolError):
        dispatch(b, "vote_poll", {"poll_id": p, "person_id": "mia", "option": "Miami"})


def test_itinerary_saved_only_with_draft_id(b):
    d = dispatch(b, "generate_itinerary", {"trip_id": "t"})
    assert len(d["days"]) == 5 and b.trips["t"].activities == []
    s = dispatch(b, "generate_itinerary", {"trip_id": "t", "save_draft_id": d["draft_id"]})
    assert len(s["activity_ids"]) == 10


def test_unknown_args_are_tool_errors(b):
    with pytest.raises(ToolError):
        dispatch(b, "get_balances", {"trip_id": "t", "bogus": 1})
    with pytest.raises(ToolError):
        dispatch(b, "nope", {})
