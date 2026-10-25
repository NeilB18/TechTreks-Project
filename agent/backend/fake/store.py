"""FakeBackend: an in-memory implementation of the Backend protocol.

Enforces data rules (splits, opt-outs, leftover cents, refund ratios, dropouts
keep past splits). The money rules come from classes/ through ledger.py. It does
NOT enforce confirmations; whether the agent asked first is checked by the
scenario tests.
"""

import re
from datetime import date, datetime

from agent.backend.fake import ledger, rules
from agent.backend.fake.models import (
    APPROVAL_TYPES, CATEGORIES, STATUSES, Activity, Budget, Expense, Person, Poll,
    Refund, Reminder, Trip,
)
from agent.backend.protocol import ToolError

TRIP_FIELDS = ["destination", "start_date", "end_date", "base_currency", "status",
               "target_break", "group_budget", "leader_id", "leader_approval", "name",
               "auto_log_mode"]

# Canned "external API" content until Google Places / SerpAPI are wired up.
FAKE_TIPS = {
    "budget": {"lodging": "Hostel or a shared room a bit outside the center",
               "food": "Street food, food trucks and grocery-store breakfasts",
               "activities": "Free beach days, walking tours and public parks",
               "saving_tips": "Use public transit or bikes instead of rideshares"},
    "mid": {"lodging": "Shared Airbnb in a central neighborhood",
            "food": "Casual local spots plus one nice group dinner",
            "activities": "One paid group activity (boat tour, museum) plus free days",
            "saving_tips": "Book the big activity early and split groceries"},
    "splurge": {"lodging": "Hotel in the main strip",
                "food": "Sit-down dinners most nights",
                "activities": "Several paid activities and a night out",
                "saving_tips": "Bundle bookings and watch for group discounts"},
}
FAKE_ITINERARY_ITEMS = [
    ("Beach day", "Main beach", 0),
    ("Walking tour", "Old town", 2000),
    ("Group dinner", "Local restaurant", 4500),
    ("Boat tour", "Marina", 10000),
    ("Museum visit", "City museum", 2500),
    ("Night out", "Downtown", 6000),
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "x"


class FakeBackend:
    def __init__(self, now: str = "2027-03-01T12:00:00"):
        self.trips: dict[str, Trip] = {}
        self.now = now
        self._counters: dict[str, int] = {}

    # ------------------------------------------------------------------ helpers
    def _next_id(self, prefix: str, taken: set[str]) -> str:
        n = self._counters.get(prefix, 0)
        while True:
            n += 1
            if f"{prefix}{n}" not in taken:
                self._counters[prefix] = n
                return f"{prefix}{n}"

    # Expense and poll ids must be unique across trips (tools look them up without a trip_id).
    # DjangoBackend overrides these to check the database.
    def _all_expense_ids(self) -> set[str]:
        return {e.id for t in self.trips.values() for e in t.expenses}

    def _all_poll_ids(self) -> set[str]:
        return {p.id for t in self.trips.values() for p in t.polls}

    def _trip(self, trip_id: str) -> Trip:
        if trip_id not in self.trips:
            raise ToolError(f"No trip with id {trip_id!r}")
        return self.trips[trip_id]

    def _person(self, trip: Trip, pid: str, active_only: bool = False) -> Person:
        if pid not in trip.members:
            raise ToolError(f"{pid!r} is not a member of trip {trip.id!r}. Members: {sorted(trip.members)}")
        p = trip.members[pid]
        if active_only and not p.active:
            raise ToolError(f"{pid!r} has been removed from the trip and can't be in new splits or activities")
        return p

    def _find_expense(self, expense_id: str) -> tuple[Trip, Expense]:
        for t in self.trips.values():
            for e in t.expenses:
                if e.id == expense_id:
                    return t, e
        raise ToolError(f"No expense with id {expense_id!r}")

    def _find_poll(self, poll_id: str) -> tuple[Trip, Poll]:
        for t in self.trips.values():
            for p in t.polls:
                if p.id == poll_id:
                    return t, p
        raise ToolError(f"No poll with id {poll_id!r}")

    @staticmethod
    def _check_category(category: str) -> None:
        if category not in CATEGORIES:
            raise ToolError(f"Unknown category {category!r}. Use one of {CATEGORIES}")

    def _to_base(self, trip: Trip, amount: int, currency: str) -> tuple[int, float]:
        try:
            return rules.convert(amount, currency, trip.base_currency)
        except ValueError as e:
            raise ToolError(str(e)) from e

    def _compute_splits(self, trip: Trip, *, paid_by: str, amount: int, currency: str, category: str,
                        split_with: list[str] | None, exact_amounts: dict[str, int] | None,
                        percentages: dict[str, float] | None,
                        exclude: list[str] | None, override_opt_outs: list[str] | None):
        """Returns base amount, FX rate, net-change splits and auto-excluded people."""
        self._check_category(category)
        if category == "SETTLEMENT":
            raise ToolError("Paybacks go through record_payback, not log_expense")
        self._person(trip, paid_by)
        if amount <= 0:
            raise ToolError("amount must be a positive number of cents")
        base_amount, rate = self._to_base(trip, amount, currency)
        auto_excluded = []
        if sum(x is not None for x in (split_with, exact_amounts, percentages)) != 1:
            raise ToolError("Pass exactly one of split_with, exact_amounts or percentages")
        if exact_amounts is not None:
            for pid in exact_amounts:
                self._person(trip, pid, active_only=True)
            if sum(exact_amounts.values()) != amount:
                raise ToolError(f"exact_amounts sum to {sum(exact_amounts.values())}, but amount is {amount}")
            shares = (dict(exact_amounts) if currency == trip.base_currency
                      else rules.split_proportional(base_amount, exact_amounts))
            splits = ledger.split(base_amount, paid_by, shares=shares)
        elif percentages is not None:
            for pid in percentages:
                self._person(trip, pid, active_only=True)
            splits = ledger.split(base_amount, paid_by, percents=percentages)
        else:
            excluded = set(exclude or [])
            overrides = set(override_opt_outs or [])
            people = []
            for pid in dict.fromkeys(split_with):  # dedupe, keep order
                self._person(trip, pid, active_only=True)
                if pid in excluded:
                    continue
                if (pid, category) in trip.exclusions and pid not in overrides:
                    auto_excluded.append({"person_id": pid, "reason": f"opted out of {category}"})
                    continue
                people.append(pid)
            if not people:
                raise ToolError("Nobody left in the split after exclusions")
            splits = ledger.split(base_amount, paid_by, people=people)
        return base_amount, rate, splits, auto_excluded

    def _expense_view(self, trip: Trip, e: Expense) -> dict:
        return {
            "expense_id": e.id, "description": e.description, "category": e.category,
            "paid_by": e.paid_by, "amount_cents": e.amount_cents,
            "original_amount": e.original_amount, "original_currency": e.original_currency,
            "fx_rate": e.fx_rate, "shares": ledger.shares(e), "splits": e.splits,
            "created_at": e.created_at,
            "refunded_cents": sum(r.amount_cents for r in trip.refunds if r.expense_id == e.id),
        }

    def _activity_view(self, trip: Trip, a: Activity) -> dict:
        n = len(a.attendees)
        per_person = (a.est_cost_cents if a.cost_is_per_person or a.est_cost_cents is None or n == 0
                      else round(a.est_cost_cents / n))
        return {"activity_id": a.id, "name": a.name, "location": a.location, "start": a.start,
                "end": a.end, "est_cost_cents": a.est_cost_cents,
                "cost_is_per_person": a.cost_is_per_person, "est_per_person_cents": per_person,
                "attendees": a.attendees, "important": a.important,
                "booking_url": a.booking_url, "expense_id": a.expense_id}

    @staticmethod
    def _when(value: str, field: str) -> datetime:
        # Naive datetimes, so a timezone-aware "now" from Django compares with chat-entered times.
        try:
            return datetime.fromisoformat(value).replace(tzinfo=None)
        except (TypeError, ValueError) as e:
            raise ToolError(f"{field} must be ISO, like 2027-03-12T18:00") from e

    def _poll_open(self, p: Poll) -> bool:
        """A poll closes itself once closes_at has passed."""
        return p.is_open and not (p.closes_at and self._when(self.now, "now") >= self._when(p.closes_at, "closes_at"))

    def _activities_outside(self, trip: Trip) -> list[str]:
        if not (trip.start_date and trip.end_date):
            return []
        out = []
        for a in trip.activities:
            if a.start and not (trip.start_date <= a.start[:10] <= trip.end_date):
                out.append(a.id)
        return out

    # ------------------------------------------------------------------ seeding
    def load_seed(self, seed: dict) -> None:
        """Build a trip from a scenario 'seed' block (see tests/scenarios/*.yaml)."""
        if "now" in seed:
            self.now = str(seed["now"])
        t = seed["trip"]
        trip = Trip(id=t["id"], name=t.get("name", t["id"]),
                    **{k: t[k] for k in TRIP_FIELDS if k in t and k not in ("name",)})
        if "leader" in t:
            trip.leader_id = t["leader"]
        self.trips[trip.id] = trip
        for m in seed.get("members", []):
            trip.members[m["id"]] = Person(id=m["id"], name=m["name"],
                                           chat_user_id=m.get("chat_user_id", m["id"]),
                                           payment_handle=m.get("handle"),
                                           active=m.get("active", True))
        for pid, b in (seed.get("budgets") or {}).items():
            trip.budgets[pid] = Budget(owner_id=pid, total_cents=b["total"], limits=b.get("limits", {}))
        for pid, cat in seed.get("exclusions", []):
            trip.exclusions.add((pid, cat))
        for e in seed.get("expenses", []):
            self.log_expense(trip_id=trip.id, paid_by=e["paid_by"], amount=e["amount"],
                             currency=e.get("currency", trip.base_currency),
                             description=e["description"], category=e["category"],
                             split_with=e["split_with"])
            if "id" in e:
                trip.expenses[-1].id = e["id"]
        for pb in seed.get("paybacks", []):
            self.record_payback(trip_id=trip.id, from_person=pb["from"], to_person=pb["to"],
                                amount=pb["amount"], currency=trip.base_currency)
            if "id" in pb:
                trip.expenses[-1].id = pb["id"]
        for a in seed.get("activities", []):
            a = dict(a)
            a.setdefault("attendees", trip.active_member_ids())
            trip.activities.append(Activity(**a))
        for p in seed.get("polls", []):
            trip.polls.append(Poll(**p))

    # ================================================================= TOOLS
    # ---------------------------------------------------------------- expenses
    def log_expense(self, trip_id: str, paid_by: str, amount: int, currency: str, description: str,
                    category: str, split_with: list[str] | None = None,
                    exact_amounts: dict[str, int] | None = None,
                    percentages: dict[str, float] | None = None, exclude: list[str] | None = None,
                    override_opt_outs: list[str] | None = None, source_message: str = "") -> dict:
        trip = self._trip(trip_id)
        base_amount, rate, splits, auto_excluded = self._compute_splits(
            trip, paid_by=paid_by, amount=amount, currency=currency, category=category,
            split_with=split_with, exact_amounts=exact_amounts, percentages=percentages,
            exclude=exclude, override_opt_outs=override_opt_outs)
        e = Expense(id=self._next_id("e", self._all_expense_ids()), paid_by=paid_by,
                    amount_cents=base_amount, original_amount=amount, original_currency=currency,
                    fx_rate=rate, description=description, category=category, splits=splits,
                    created_at=self.now, source_message=source_message)
        trip.expenses.append(e)
        return {"expense_id": e.id, "base_amount": base_amount, "base_currency": trip.base_currency,
                "original_amount": amount, "original_currency": currency, "fx_rate": rate,
                "shares": ledger.shares(e), "splits": splits, "auto_excluded": auto_excluded}

    def edit_expense(self, expense_id: str, requested_by: str, changes: dict) -> dict:
        trip, e = self._find_expense(expense_id)
        self._person(trip, requested_by)
        if e.category == "SETTLEMENT":
            raise ToolError("That's a payback, not an expense; delete it and record the payback again")
        allowed = {"amount", "currency", "description", "category", "split_with", "exact_amounts",
                   "percentages", "exclude", "override_opt_outs", "paid_by"}
        bad = set(changes) - allowed
        if bad:
            raise ToolError(f"Can't change {sorted(bad)}; allowed: {sorted(allowed)}")
        if "description" in changes:
            e.description = changes["description"]
        money_keys = {"amount", "currency", "category", "split_with", "exact_amounts", "percentages",
                      "exclude", "override_opt_outs", "paid_by"}
        if money_keys & set(changes):
            split_with = changes.get("split_with")
            exact = changes.get("exact_amounts")
            percentages = changes.get("percentages")
            if split_with is None and exact is None and percentages is None:
                split_with = list(ledger.shares(e))  # keep the same people
            amount = changes.get("amount", e.original_amount)
            currency = changes.get("currency", e.original_currency)
            category = changes.get("category", e.category)
            paid_by = changes.get("paid_by", e.paid_by)
            base_amount, rate, splits, auto_excluded = self._compute_splits(
                trip, paid_by=paid_by, amount=amount, currency=currency, category=category,
                split_with=split_with, exact_amounts=exact, percentages=percentages,
                exclude=changes.get("exclude"), override_opt_outs=changes.get("override_opt_outs"))
            e.amount_cents, e.fx_rate, e.splits = base_amount, rate, splits
            e.original_amount, e.original_currency, e.category, e.paid_by = amount, currency, category, paid_by
        return {"updated": True, "payer": e.paid_by, "expense": self._expense_view(trip, e)}

    def delete_expense(self, expense_id: str, requested_by: str) -> dict:
        trip, e = self._find_expense(expense_id)
        self._person(trip, requested_by)
        trip.expenses.remove(e)
        trip.refunds = [r for r in trip.refunds if r.expense_id != expense_id]
        for a in trip.activities:
            if a.expense_id == expense_id:
                a.expense_id = None
        return {"deleted": True, "expense_id": expense_id, "payer": e.paid_by}

    def record_refund(self, expense_id: str, amount: int, currency: str, note: str = "") -> dict:
        trip, e = self._find_expense(expense_id)
        if e.category == "SETTLEMENT":
            raise ToolError("Paybacks can't be refunded; delete it instead")
        if amount <= 0:
            raise ToolError("amount must be a positive number of cents")
        base, _ = self._to_base(trip, amount, currency)
        already = sum(r.amount_cents for r in trip.refunds if r.expense_id == expense_id)
        if base + already > e.amount_cents:
            raise ToolError(f"Refunds would total {base + already} cents, more than the expense ({e.amount_cents})")
        per_person = ledger.refund_shares(e, base)
        r = Refund(id=self._next_id("r", {r.id for r in trip.refunds}), expense_id=expense_id,
                   amount_cents=base, original_amount=amount, currency=currency, note=note,
                   per_person=per_person, created_at=self.now)
        trip.refunds.append(r)
        return {"refund_id": r.id, "expense_id": expense_id, "payer": e.paid_by,
                "base_amount": base, "per_person": per_person}

    def record_payback(self, trip_id: str, from_person: str, to_person: str, amount: int,
                       currency: str) -> dict:
        trip = self._trip(trip_id)
        if amount <= 0:
            raise ToolError("amount must be a positive number of cents")
        base, rate = self._to_base(trip, amount, currency)
        s = ledger.record_payback(trip, from_person, to_person, base,
                                  self._next_id("e", self._all_expense_ids()))
        e = Expense(id=s.id, paid_by=from_person, amount_cents=base, original_amount=amount,
                    original_currency=currency, fx_rate=rate, description=s.description,
                    category="SETTLEMENT", splits=s.splits, created_at=self.now)
        trip.expenses.append(e)
        return {"expense_id": e.id, "from": from_person, "to": to_person, "base_amount": base,
                "base_currency": trip.base_currency, "original_amount": amount,
                "original_currency": currency}

    # ---------------------------------------------------------- trip & members
    def add_member(self, trip_id: str, chat_user_id: str, name: str, payment_handle: str | None = None) -> dict:
        trip = self._trip(trip_id)
        for p in trip.members.values():
            if p.chat_user_id == chat_user_id:
                p.active = True
                p.name = name or p.name
                p.payment_handle = payment_handle or p.payment_handle
                return {"person_id": p.id, "added": True, "rejoined": True}
        pid = _slug(name)
        while pid in trip.members:
            pid += "_2"
        trip.members[pid] = Person(id=pid, name=name, chat_user_id=chat_user_id, payment_handle=payment_handle)
        return {"person_id": pid, "added": True, "rejoined": False}

    def remove_member(self, trip_id: str, person_id: str) -> dict:
        trip = self._trip(trip_id)
        p = self._person(trip, person_id)
        if not p.active:
            raise ToolError(f"{person_id!r} was already removed")
        p.active = False
        removed_from = []
        for a in trip.activities:
            if person_id in a.attendees:
                a.attendees.remove(person_id)
                removed_from.append(a.id)
        return {"removed": True, "removed_from_activities": removed_from,
                "still_owes_past_splits": True, "was_leader": trip.leader_id == person_id}

    def update_trip(self, trip_id: str, changes: dict) -> dict:
        trip = self._trip(trip_id)
        bad = set(changes) - set(TRIP_FIELDS)
        if bad:
            raise ToolError(f"Can't change {sorted(bad)}; allowed: {TRIP_FIELDS}")
        if "status" in changes and changes["status"] not in STATUSES:
            raise ToolError(f"status must be one of {STATUSES}")
        if "leader_id" in changes:
            self._person(trip, changes["leader_id"], active_only=True)
        if "leader_approval" in changes:
            bad = set(changes["leader_approval"]) - set(APPROVAL_TYPES)
            if bad:
                raise ToolError(f"Unknown leader_approval types {sorted(bad)}; use {APPROVAL_TYPES}")
        if "base_currency" in changes and changes["base_currency"] != trip.base_currency:
            if changes["base_currency"] not in rules.USD_PER_UNIT:
                raise ToolError(f"Unsupported currency {changes['base_currency']!r}")
            if trip.expenses:
                raise ToolError("Can't change base_currency after expenses are logged")
        for k in ("start_date", "end_date"):
            if k in changes and changes[k] is not None:
                try:
                    date.fromisoformat(changes[k])
                except (TypeError, ValueError) as e:
                    raise ToolError(f"{k} must be an ISO date like 2027-03-16") from e
        new_start = changes.get("start_date", trip.start_date)
        new_end = changes.get("end_date", trip.end_date)
        if new_start and new_end and new_start > new_end:
            raise ToolError("start_date is after end_date")
        for k, v in changes.items():
            setattr(trip, k, v)
        out = {"updated": True, "trip": self.summary(trip_id)["trip"]}
        if "start_date" in changes or "end_date" in changes:
            out["activities_outside_dates"] = self._activities_outside(trip)
        if "group_budget" in changes and changes["group_budget"] is not None:
            # Names only, never amounts: the agent uses this to DM people privately.
            out["members_below_group_budget"] = sorted(
                pid for pid, b in trip.budgets.items()
                if trip.members[pid].active and b.total_cents < changes["group_budget"])
            out["members_without_budget"] = sorted(
                pid for pid in trip.active_member_ids() if pid not in trip.budgets)
        return out

    def set_budget(self, trip_id: str, person_id: str, total: int, limits: dict[str, int] | None = None) -> dict:
        trip = self._trip(trip_id)
        self._person(trip, person_id)
        if total < 0:
            raise ToolError("total must be >= 0 cents")
        for cat in (limits or {}):
            self._check_category(cat)
        trip.budgets[person_id] = Budget(owner_id=person_id, total_cents=total, limits=dict(limits or {}))
        return {"saved": True, "person_id": person_id, "total_cents": total, "limits": limits or {}}

    def set_exclusion(self, trip_id: str, person_id: str, category: str, remove: bool = False) -> dict:
        trip = self._trip(trip_id)
        self._person(trip, person_id)
        self._check_category(category)
        if remove:
            trip.exclusions.discard((person_id, category))
        else:
            trip.exclusions.add((person_id, category))
        return {"saved": True, "person_id": person_id, "category": category, "opted_out": not remove}

    # ---------------------------------------------------------------- planning
    def generate_itinerary(self, trip_id: str, constraints: str | None = None,
                           save_draft_id: str | None = None) -> dict:
        trip = self._trip(trip_id)
        if save_draft_id:
            if save_draft_id not in trip.itinerary_drafts:
                raise ToolError(f"No draft {save_draft_id!r}")
            ids = []
            for day in trip.itinerary_drafts.pop(save_draft_id):
                for item in day["items"]:
                    a = Activity(id=self._next_id("a", {a.id for a in trip.activities}),
                                 attendees=trip.active_member_ids(),
                                 **{k: item[k] for k in ("name", "location", "start", "end",
                                                         "est_cost_cents", "cost_is_per_person")})
                    trip.activities.append(a)
                    ids.append(a.id)
            return {"saved": True, "activity_ids": ids}
        if not (trip.destination and trip.start_date and trip.end_date):
            raise ToolError("Set destination, start_date and end_date before generating an itinerary")
        start, end = date.fromisoformat(trip.start_date), date.fromisoformat(trip.end_date)
        days = []
        for i in range((end - start).days + 1):
            d = date.fromordinal(start.toordinal() + i).isoformat()
            items = []
            for j, hour in enumerate((11, 19)):
                name, loc, cost = FAKE_ITINERARY_ITEMS[(2 * i + j) % len(FAKE_ITINERARY_ITEMS)]
                items.append({"name": name, "location": f"{loc}, {trip.destination}",
                              "start": f"{d}T{hour}:00", "end": f"{d}T{hour + 2}:00",
                              "est_cost_cents": cost, "cost_is_per_person": True})
            days.append({"date": d, "items": items})
        draft_id = self._next_id("d", set(trip.itinerary_drafts))
        trip.itinerary_drafts[draft_id] = days
        return {"draft_id": draft_id, "days": days, "constraints": constraints, "source": "fake",
                "saved": False}

    def add_activity(self, trip_id: str, name: str | None = None, activity_id: str | None = None,
                     location: str | None = None, start: str | None = None, end: str | None = None,
                     est_cost_cents: int | None = None, cost_is_per_person: bool | None = None,
                     attendees: list[str] | None = None, important: bool | None = None,
                     booking_url: str | None = None, expense_id: str | None = None) -> dict:
        trip = self._trip(trip_id)
        for pid in attendees or []:
            self._person(trip, pid, active_only=True)
        fields = {"name": name, "location": location, "start": start, "end": end,
                  "est_cost_cents": est_cost_cents, "cost_is_per_person": cost_is_per_person,
                  "attendees": attendees, "important": important, "booking_url": booking_url,
                  "expense_id": expense_id}
        fields = {k: v for k, v in fields.items() if v is not None}
        match = [a for a in trip.activities if a.id == activity_id] if activity_id else []
        if activity_id and not match:
            raise ToolError(f"No activity {activity_id!r}")
        new_start = fields.get("start", match[0].start if match else None)
        new_end = fields.get("end", match[0].end if match else None)
        if new_start and new_end and self._when(new_end, "end") < self._when(new_start, "start"):
            raise ToolError("An activity can't end before it starts")
        if activity_id:
            for k, v in fields.items():
                setattr(match[0], k, v)
            return {"activity_id": activity_id, "updated": True}
        if not name:
            raise ToolError("name is required for a new activity")
        fields.setdefault("attendees", trip.active_member_ids())
        a = Activity(id=self._next_id("a", {a.id for a in trip.activities}), **fields)
        trip.activities.append(a)
        return {"activity_id": a.id, "created": True, "outside_trip_dates": a.id in self._activities_outside(trip)}

    def get_travel_tips(self, trip_id: str, destination: str, multipliers: list[float],
                        prices_only: bool = False, interests: list[str] | None = None) -> dict:
        trip = self._trip(trip_id)
        if not multipliers or any(m <= 0 for m in multipliers):
            raise ToolError("multipliers must be positive numbers, e.g. [0.5, 0.75, 1, 1.25, 1.5, 2]")
        active = trip.active_member_ids()
        totals = [trip.budgets[p].total_cents for p in active if p in trip.budgets]
        missing = [p for p in active if p not in trip.budgets]
        if not totals:
            return {"average_cents": None, "missing_budgets": missing, "tiers": [],
                    "note": "Nobody has set a budget yet; DM members to collect them."}
        avg = round(sum(totals) / len(totals))
        tiers = []
        for m in multipliers:
            tier = {"multiplier": m, "budget_cents": rules.tier_price(avg, m)}
            if not prices_only:
                level = "budget" if m < 0.75 else "mid" if m < 1.25 else "splurge"
                tier.update(FAKE_TIPS[level], source="fake")
            tiers.append(tier)
        return {"destination": destination, "average_cents": avg, "budgets_counted": len(totals),
                "missing_budgets": missing, "tiers": tiers, "interests": interests or []}

    def create_poll(self, trip_id: str, question: str, options: list[str], closes_at: str | None = None) -> dict:
        trip = self._trip(trip_id)
        if len(options) < 2:
            raise ToolError("A poll needs at least 2 options")
        if closes_at is not None:
            self._when(closes_at, "closes_at")
        p = Poll(id=self._next_id("p", self._all_poll_ids()), question=question,
                 options=list(options), closes_at=closes_at)
        trip.polls.append(p)
        return {"poll_id": p.id, "options": p.options, "closes_at": closes_at}

    def vote_poll(self, poll_id: str, person_id: str, option: str) -> dict:
        trip, p = self._find_poll(poll_id)
        self._person(trip, person_id, active_only=True)
        if not self._poll_open(p):
            raise ToolError("That poll is closed")
        if option not in p.options:
            raise ToolError(f"{option!r} isn't an option. Options: {p.options}")
        p.votes[person_id] = option
        return {"recorded": True, "votes_so_far": len(p.votes), "voters_left": [
            m for m in trip.active_member_ids() if m not in p.votes]}

    def close_poll(self, poll_id: str) -> dict:
        _, p = self._find_poll(poll_id)
        p.is_open = False
        counts = {o: 0 for o in p.options}
        for o in p.votes.values():
            counts[o] += 1
        top = max(counts.values())
        leaders = [o for o, c in counts.items() if c == top and top > 0]
        return {"poll_id": p.id, "question": p.question, "counts": counts,
                "winner": leaders[0] if len(leaders) == 1 else None,
                "tie": leaders if len(leaders) > 1 else []}

    def create_reminder(self, trip_id: str, message: str, due_at: str, audience: list[str] | str) -> dict:
        trip = self._trip(trip_id)
        if audience in ("all", ["all"]):
            audience = "all"
        else:
            for pid in audience:
                self._person(trip, pid)
        try:
            datetime.fromisoformat(due_at)
        except (TypeError, ValueError) as e:
            raise ToolError("due_at must be ISO, like 2027-03-12T18:00") from e
        r = Reminder(id=self._next_id("m", {r.id for r in trip.reminders}), message=message,
                     due_at=due_at, audience=audience)
        trip.reminders.append(r)
        return {"reminder_id": r.id, "due_at": due_at, "audience": audience}

    # ------------------------------------------------------ money info & reads
    def settle_up(self, trip: Trip) -> dict[tuple[str, str], int]:
        """(from, to) -> cents: the suggested payments, netted across the group."""
        return {(d, c): amt for d, c, amt in ledger.settle_up(trip)}

    def get_balances(self, trip_id: str) -> dict:
        trip = self._trip(trip_id)
        return {
            "net_balances": ledger.net_balances(trip),
            "suggested_payments": [
                {"from": d, "to": c, "amount_cents": amt, "handle": trip.members[c].payment_handle}
                for d, c, amt in ledger.settle_up(trip)],
            "currency": trip.base_currency,
        }

    def _planned_by_category(self, trip: Trip, pid: str) -> dict[str, int]:
        planned = 0
        for a in trip.activities:
            if pid in a.attendees and a.expense_id is None and a.est_cost_cents \
                    and (a.start is None or a.start[:10] >= self.now[:10]):
                planned += self._activity_view(trip, a)["est_per_person_cents"]
        return {"ACTIVITIES": planned} if planned else {}

    def get_budget_status(self, trip_id: str, person_id: str) -> dict:
        trip = self._trip(trip_id)
        self._person(trip, person_id)
        b = trip.budgets.get(person_id)
        spent_by_cat = ledger.spent_by_category(trip, person_id)
        planned_by_cat = self._planned_by_category(trip, person_id)
        spent, planned = sum(spent_by_cat.values()), sum(planned_by_cat.values())
        if b is None:
            return {"person_id": person_id, "budget_set": False, "spent_cents": spent,
                    "planned_cents": planned, "warnings": []}
        cats = sorted(set(b.limits) | set(spent_by_cat) | set(planned_by_cat))
        return {
            "person_id": person_id, "budget_set": True, "visibility": "DM only",
            "total_cents": b.total_cents, "spent_cents": spent,
            "remaining_cents": b.total_cents - spent, "planned_cents": planned,
            "remaining_after_planned_cents": b.total_cents - spent - planned,
            "by_category": {c: {"limit_cents": b.limits.get(c), "spent_cents": spent_by_cat.get(c, 0),
                                "planned_cents": planned_by_cat.get(c, 0)} for c in cats},
            "warnings": ledger.budget_warnings(trip, person_id, planned_by_cat),
        }

    def convert_currency(self, amount: int, **kw) -> dict:
        # "from" is a Python keyword, so it arrives through **kw.
        from_ccy, to_ccy = kw.pop("from", None), kw.pop("to", None)
        if kw or not from_ccy or not to_ccy:
            raise ToolError("convert_currency takes amount, from, to")
        try:
            converted, rate = rules.convert(amount, from_ccy, to_ccy)
        except ValueError as e:
            raise ToolError(str(e)) from e
        return {"amount": amount, "from": from_ccy, "to": to_ccy, "converted": converted,
                "rate": rate, "source": "fixed table (placeholder)"}

    def get_trip(self, trip_id: str) -> dict:
        trip = self._trip(trip_id)
        s = self.summary(trip_id)
        s["expenses"] = [self._expense_view(trip, e) for e in trip.expenses]
        s["refunds"] = [vars(r) for r in trip.refunds]
        s["polls"] = [vars(p) | {"is_open": self._poll_open(p)} for p in trip.polls]
        s["reminders"] = [vars(r) for r in trip.reminders]
        s["itinerary_drafts"] = sorted(trip.itinerary_drafts)
        return s

    # ------------------------------------------------------------- not a tool
    def summary(self, trip_id: str) -> dict:
        trip = self._trip(trip_id)
        return {
            "trip": {"id": trip.id, "name": trip.name, "status": trip.status,
                     "destination": trip.destination, "start_date": trip.start_date,
                     "end_date": trip.end_date, "target_break": trip.target_break,
                     "base_currency": trip.base_currency, "group_budget_cents": trip.group_budget,
                     "leader_id": trip.leader_id, "leader_approval": sorted(trip.leader_approval),
                     "auto_log_mode": trip.auto_log_mode},
            "members": [{"id": p.id, "name": p.name, "handle": p.payment_handle,
                         "active": p.active, "budget_set": p.id in trip.budgets}
                        for p in trip.members.values()],
            "category_opt_outs": sorted([pid, cat] for pid, cat in trip.exclusions),
            "recent_expenses": [
                {"id": e.id, "description": e.description, "category": e.category,
                 "paid_by": e.paid_by, "amount_cents": e.amount_cents, "shares": ledger.shares(e)}
                for e in trip.expenses[-10:]],
            "activities": [self._activity_view(trip, a) for a in trip.activities],
            "open_polls": [{"id": p.id, "question": p.question, "options": p.options,
                            "votes": len(p.votes)} for p in trip.polls if self._poll_open(p)],
        }
