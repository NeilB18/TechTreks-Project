"""The checker must catch the mistakes the live tests exist to catch."""

import copy

from agent.scenarios import load_scenarios, run_scenario

SCN = {s["file"]: s for s in load_scenarios()}


def mutate(file, turn, **golden):
    scn = copy.deepcopy(SCN[file])
    scn["turns"][turn]["golden"].update(golden)
    return run_scenario(scn)


def test_catches_acting_before_confirmation():
    fails = mutate("ex1_dropout.yaml", 0, calls=[
        {"name": "remove_member", "args": {"trip_id": "miami", "person_id": "priya"}}])
    assert any("changed state before confirmation" in f for f in fails)
    assert any("forbidden call remove_member" in f for f in fails)


def test_catches_budget_leak_in_group():
    fails = mutate("ex5_travel_tips.yaml", 2, messages=[
        {"to": "group", "text": "Locked in ~$917. Mia, your $500 is below that."},
        {"to": "mia", "text": "~$917 is above your budget"},
        {"to": "aarav", "text": "Mia is below"}])
    assert any("PRIVACY" in f and "mia" in f for f in fails)


def test_catches_wrong_split_and_balance():
    fails = mutate("ex7b_payer_outside_split.yaml", 0, calls=[
        {"name": "log_expense", "args": {"trip_id": "miami", "paid_by": "jake", "amount": 35000,
                                         "currency": "USD", "description": "Bar tab", "category": "DRINKS",
                                         "split_with": ["aarav", "priya", "jake", "mia", "sam", "leo",
                                                        "nina", "zoe"],
                                         "override_opt_outs": ["jake"]}}])
    assert any("aarav should owe jake 5000" in f for f in fails)


def test_catches_missing_dm():
    fails = mutate("ex9_refund.yaml", 1, messages=[
        {"to": "group", "text": "Refund logged, Mia now owes Aarav $50"}])
    assert any("no message sent to aarav" in f for f in fails)
