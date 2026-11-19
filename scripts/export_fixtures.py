"""Write web/fixtures/*.json for the trip page, using the real backend logic.

Each examples.md scenario is replayed (golden tool calls) through TripEngine, and
a fuller demo trip is built too. The JSON is exactly what GET /api/trips/<id> and
/balances return, so the page is built against the real contract.

    .venv/bin/python scripts/export_fixtures.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.backend.core.engine import TripEngine  # noqa: E402
from agent.scenarios import golden_turn, load_scenarios  # noqa: E402

OUT = ROOT / "web" / "fixtures"
PEOPLE = ["aarav", "priya", "jake", "mia", "sam", "leo"]


def page_data(backend: TripEngine, trip_id: str) -> dict:
    return {"detail": backend.get_trip(trip_id), "balances": backend.get_balances(trip_id),
            "budgets": backend.budget_overview(trip_id)}


def demo(backend=None, trip_id: str = "miami-demo") -> dict:
    b = backend if backend is not None else TripEngine()
    b.load_seed({
        "now": "2027-03-01T12:00:00",
        "trip": {"id": trip_id, "name": "Miami Spring Break", "status": "BOOKED", "destination": "Miami",
                 "start_date": "2027-03-14", "end_date": "2027-03-18", "base_currency": "USD",
                 "group_budget": 91700, "leader": "aarav",
                 "leader_approval": ["member_changes", "trip_changes"]},
        # Jake uses Zelle (an email handle) so the page shows both payment styles; with netted
        # settle-up he's still owed money, so he appears as a receiver.
        "members": [{"id": p, "name": p.title(),
                     "handle": "jake@example.com" if p == "jake" else f"@{p}-venmo"} for p in PEOPLE],
        "exclusions": [["jake", "DRINKS"]],
    })
    t = trip_id
    b.update_trip(trip_id=t, changes={"lodging": "Freehand Miami, 2727 Indian Creek Dr"})
    # What the group told the bot: some plans with just a day, some in a slot, some at a clock time.
    plan = [("Check in at the Airbnb", {"start": "2027-03-14T15:00"}),
            ("South Pointe Park", {"day": "2027-03-14"}),
            ("Joe's Stone Crab", {"day": "2027-03-14", "slot": "dinner", "est_cost_cents": 7000}),
            ("Wynwood Walls", {"day": "2027-03-15", "slot": "morning"}),
            ("Versailles Restaurant", {"day": "2027-03-15", "slot": "lunch", "est_cost_cents": 2500}),
            ("Ball & Chain", {"day": "2027-03-15", "slot": "night", "est_cost_cents": 3000}),
            ("Vizcaya Museum and Gardens", {"day": "2027-03-16", "slot": "afternoon", "est_cost_cents": 2500}),
            ("La Mar by Gastón Acurio", {"day": "2027-03-16", "slot": "dinner", "est_cost_cents": 6000}),
            ("Beach day", {"day": "2027-03-17"}),
            ("Little Havana Walking Tour", {"day": "2027-03-17", "slot": "morning", "est_cost_cents": 2000}),
            ("Bayside Marketplace", {"day": "2027-03-18", "slot": "lunch"})]
    for name, when in plan:
        b.add_activity(trip_id=t, name=name, **when)
    b.add_activity(trip_id=t, name="Boat tour", location="Miami Beach Marina", start="2027-03-15T14:00",
                   est_cost_cents=60000, cost_is_per_person=False, important=True)
    b.save_idea(trip_id=t, name="Mandolin Aegean Bistro", est_cost_cents=4000, suggested_by="mia")
    b.save_idea(trip_id=t, name="Key Biscayne bike ride", suggested_by="leo")
    log = dict(trip_id=t, currency="USD")
    b.log_expense(**log, paid_by="aarav", amount=150000, description="Airbnb (Mar 14–18)",
                  category="LODGING", split_with=PEOPLE)
    b.log_expense(**log, paid_by="jake", amount=35000, description="Bar tab", category="DRINKS",
                  split_with=PEOPLE)
    b.log_expense(**log, paid_by="mia", amount=12000, description="Dinner", category="FOOD",
                  split_with=PEOPLE, exclude=["leo"])
    b.log_expense(trip_id=t, paid_by="sam", amount=180000, currency="MXN", description="Snorkel day trip",
                  category="ACTIVITIES", split_with=["sam", "mia", "leo"])
    e = b.log_expense(**log, paid_by="aarav", amount=30000, description="Concert tickets",
                      category="ACTIVITIES", split_with=["aarav", "priya", "jake"])["expense_id"]
    b.record_payback(trip_id=t, from_person="priya", to_person="aarav", amount=10000, currency="USD")
    b.record_refund(expense_id=e, amount=15000, currency="USD", note="Concert moved")
    return page_data(b, t)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    written = {"miami-demo": demo()}
    for scn in load_scenarios():
        if scn.get("skip") or scn.get("kind") == "edge":
            continue
        b = TripEngine()
        b.load_seed(scn["seed"])
        for turn in scn["turns"]:
            golden_turn(b, turn.get("golden", {}))
        trip_id = scn["seed"]["trip"]["id"]
        data = page_data(b, trip_id)
        data["detail"]["trip"]["name"] += f" (Example {scn['example']})"
        written[scn["file"].removesuffix(".yaml").replace("_", "-")] = data
    for name, data in written.items():
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, default=list) + "\n")
    print(f"wrote {len(written)} fixtures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
