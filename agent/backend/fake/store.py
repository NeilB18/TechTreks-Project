"""FakeBackend: an in-memory implementation of the Backend protocol.

Enforces data rules (splits sum to the amount, opt-outs, leftover cents,
refund ratios, dropouts keep past splits). It does NOT enforce confirmations;
whether the agent asked first is checked by the scenario tests.
"""

import random
import re
from datetime import date, datetime

from agent import config
from agent.backend.fake import rules
from agent.backend.fake.models import (
    APPROVAL_TYPES, CATEGORIES, STATUSES, Activity, Budget, Expense, Person, Poll,
    Refund, Reminder, Trip,
)
from agent.backend.protocol import ToolError
from agent.travel.provider import get_provider

TRIP_FIELDS = ["destination", "start_date", "end_date", "base_currency", "status",
               "target_break", "group_budget", "leader_id", "leader_approval", "name",
               "auto_log_mode"]

def _display(trip: Trip, amount: int, currency: str, base: int, shares: dict[str, int],
             paid_by: str | None = None) -> dict:
    """Formatted amounts to quote in chat, so replies match what was actually recorded."""
    out = {"amount": rules.fmt_money(amount, currency),
           "per_person": {p: rules.fmt_money(c, trip.base_currency) for p, c in shares.items()}}
    if currency != trip.base_currency:
        out["base_amount"] = rules.fmt_money(base, trip.base_currency)
    if paid_by:
        payer = trip.members[paid_by]
        # Everyone in the split pays the payer, so it's the payer's handle, never the debtor's.
        out["pay_to"] = f"{payer.name} ({payer.payment_handle})" if payer.payment_handle else payer.name
    return out


def _debt_line(trip: Trip, debtor: str, creditor: str, cents: int) -> str:
    c = trip.members[creditor]
    pay = f", pay {c.payment_handle}" if c.payment_handle else ""
    return f"{trip.members[debtor].name} owes {c.name} {rules.fmt_money(cents, trip.base_currency)}{pay}"


def _warnings_step(warnings: dict) -> str:
    if not warnings:
        return "Nobody's budget needs a warning."
    return (f"DM each person in budget_warnings ({', '.join(warnings)}) privately about their warning. "
            "Never mention it in the group.")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "x"


class FakeBackend:
    def __init__(self, seed: int = config.RNG_SEED, now: str = "2027-03-01T12:00:00", travel=None):
        # Travel tips/itinerary source: live Google Places + SerpAPI when keys are set, canned otherwise.
        self.travel = travel or get_provider()
        self.trips: dict[str, Trip] = {}
        self.rng = random.Random(seed)
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
                        exclude: list[str] | None, override_opt_outs: list[str] | None):
        self._check_category(category)
        self._person(trip, paid_by)
        if amount <= 0:
            raise ToolError("amount must be a positive number of cents")
        base_amount, rate = self._to_base(trip, amount, currency)
        auto_excluded = []
        if (split_with is None) == (exact_amounts is None):
            raise ToolError("Pass exactly one of split_with or exact_amounts")
        if exact_amounts is not None:
            for pid in exact_amounts:
                self._person(trip, pid, active_only=True)
            if sum(exact_amounts.values()) != amount:
                raise ToolError(f"exact_amounts sum to {sum(exact_amounts.values())}, but amount is {amount}")
            splits = (dict(exact_amounts) if currency == trip.base_currency
                      else rules.split_proportional(base_amount, exact_amounts, self.rng))
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
            splits = rules.split_equal(base_amount, people, self.rng)
        return base_amount, rate, splits, auto_excluded

    def _refunded_by_person(self, trip: Trip, expense_id: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in trip.refunds:
            if r.expense_id == expense_id:
                for p, c in r.per_person.items():
                    out[p] = out.get(p, 0) + c
        return out

    def _expense_view(self, trip: Trip, e: Expense) -> dict:
        return {
            "expense_id": e.id, "description": e.description, "category": e.category,
            "paid_by": e.paid_by, "amount_cents": e.amount_cents,
            "original_amount": e.original_amount, "original_currency": e.original_currency,
            "fx_rate": e.fx_rate, "splits": e.splits, "created_at": e.created_at,
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
            if "splits" in e:
                trip.expenses.append(Expense(
                    id=e["id"], paid_by=e["paid_by"], amount_cents=e["amount"],
                    original_amount=e["amount"], original_currency=trip.base_currency, fx_rate=1.0,
                    description=e["description"], category=e["category"], splits=dict(e["splits"]),
                    created_at=self.now))
                assert sum(e["splits"].values()) == e["amount"], e
            else:
                r = self.log_expense(trip_id=trip.id, paid_by=e["paid_by"], amount=e["amount"],
                                     currency=e.get("currency", trip.base_currency),
                                     description=e["description"], category=e["category"],
                                     split_with=e["split_with"])
                if "id" in e:
                    trip.expenses[-1].id = e["id"]
                    r["expense_id"] = e["id"]
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
                    exact_amounts: dict[str, int] | None = None, exclude: list[str] | None = None,
                    override_opt_outs: list[str] | None = None, source_message: str = "") -> dict:
        trip = self._trip(trip_id)
        base_amount, rate, splits, auto_excluded = self._compute_splits(
            trip, paid_by=paid_by, amount=amount, currency=currency, category=category,
            split_with=split_with, exact_amounts=exact_amounts, exclude=exclude,
            override_opt_outs=override_opt_outs)
        before = self._snapshot(trip, splits)
        e = Expense(id=self._next_id("e", self._all_expense_ids()), paid_by=paid_by,
                    amount_cents=base_amount, original_amount=amount, original_currency=currency,
                    fx_rate=rate, description=description, category=category, splits=splits,
                    created_at=self.now, source_message=source_message)
        trip.expenses.append(e)
        return {"expense_id": e.id, "base_amount": base_amount, "base_currency": trip.base_currency,
                "original_amount": amount, "original_currency": currency, "fx_rate": rate,
                "splits": splits, "auto_excluded": auto_excluded,
                "display": _display(trip, amount, currency, base_amount, splits, paid_by),
                "budget_warnings": (w := self._budget_warnings(trip, before)),
                "next_step": _warnings_step(w)}

    def edit_expense(self, expense_id: str, requested_by: str, changes: dict) -> dict:
        trip, e = self._find_expense(expense_id)
        self._person(trip, requested_by)
        allowed = {"amount", "currency", "description", "category", "split_with", "exact_amounts",
                   "exclude", "override_opt_outs", "paid_by"}
        bad = set(changes) - allowed
        if bad:
            raise ToolError(f"Can't change {sorted(bad)}; allowed: {sorted(allowed)}")
        if "description" in changes:
            e.description = changes["description"]
        before = {}
        money_keys = {"amount", "currency", "category", "split_with", "exact_amounts", "exclude",
                      "override_opt_outs", "paid_by"}
        if money_keys & set(changes):
            split_with = changes.get("split_with")
            exact = changes.get("exact_amounts")
            if split_with is None and exact is None:
                split_with = list(e.splits)  # keep the same people
            amount = changes.get("amount", e.original_amount)
            currency = changes.get("currency", e.original_currency)
            category = changes.get("category", e.category)
            paid_by = changes.get("paid_by", e.paid_by)
            base_amount, rate, splits, auto_excluded = self._compute_splits(
                trip, paid_by=paid_by, amount=amount, currency=currency, category=category,
                split_with=split_with, exact_amounts=exact, exclude=changes.get("exclude"),
                override_opt_outs=changes.get("override_opt_outs"))
            before = self._snapshot(trip, set(e.splits) | set(splits))
            e.amount_cents, e.fx_rate, e.splits = base_amount, rate, splits
            e.original_amount, e.original_currency, e.category, e.paid_by = amount, currency, category, paid_by
        return {"updated": True, "payer": e.paid_by, "expense": self._expense_view(trip, e),
                "budget_warnings": (w := self._budget_warnings(trip, before)),
                "next_step": _warnings_step(w)}

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
        if amount <= 0:
            raise ToolError("amount must be a positive number of cents")
        base, _ = self._to_base(trip, amount, currency)
        already = sum(r.amount_cents for r in trip.refunds if r.expense_id == expense_id)
        if base + already > e.amount_cents:
            raise ToolError(f"Refunds would total {base + already} cents, more than the expense ({e.amount_cents})")
        per_person = rules.split_proportional(base, e.splits, self.rng)
        before = self._snapshot(trip, per_person)
        r = Refund(id=self._next_id("r", {r.id for r in trip.refunds}), expense_id=expense_id,
                   amount_cents=base, original_amount=amount, currency=currency, note=note,
                   per_person=per_person, created_at=self.now)
        trip.refunds.append(r)
        payer_owes = [{"to": c, "amount_cents": amt, "handle": trip.members[c].payment_handle,
                       "line": _debt_line(trip, d, c, amt)}
                      for (d, c), amt in sorted(self.pairwise_debts(trip).items()) if d == e.paid_by]
        step = "Post the refund and changed balances in the group."
        if payer_owes:
            step += (f" {e.paid_by} now owes money back (see payer_now_owes): DM {e.paid_by} who to pay,"
                     " how much, and the handle.")
        return {"refund_id": r.id, "expense_id": expense_id, "payer": e.paid_by,
                "base_amount": base, "per_person": per_person, "payer_now_owes": payer_owes,
                "display": _display(trip, amount, currency, base, per_person),
                "budget_warnings": (w := self._budget_warnings(trip, before)),
                "next_step": step + " " + _warnings_step(w)}

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
        before = self._snapshot(trip, [m for m in trip.active_member_ids() if m != person_id])
        p.active = False
        removed_from = []
        for a in trip.activities:
            if person_id in a.attendees:
                a.attendees.remove(person_id)
                removed_from.append(a.id)
        # Group-total activities now cost the others more, so re-check everyone still going.
        warnings = self._budget_warnings(trip, before)
        return {"removed": True, "removed_from_activities": removed_from,
                "still_owes_past_splits": True, "was_leader": trip.leader_id == person_id,
                "budget_warnings": warnings, "next_step": _warnings_step(warnings)}

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
        n_days = (end - start).days + 1
        ideas = self.travel.itinerary_items(trip.destination, 2 * n_days, constraints)
        days = []
        for i in range(n_days):
            d = date.fromordinal(start.toordinal() + i).isoformat()
            items = []
            for j, hour in enumerate((11, 19)):
                name, loc, cost = ideas[2 * i + j]
                items.append({"name": name, "location": loc,
                              "start": f"{d}T{hour}:00", "end": f"{d}T{hour + 2}:00",
                              "est_cost_cents": cost, "cost_is_per_person": True})
            days.append({"date": d, "items": items})
        draft_id = self._next_id("d", set(trip.itinerary_drafts))
        trip.itinerary_drafts[draft_id] = days
        return {"draft_id": draft_id, "days": days, "constraints": constraints, "source": self.travel.source,
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
        if activity_id:
            match = [a for a in trip.activities if a.id == activity_id]
            if not match:
                raise ToolError(f"No activity {activity_id!r}")
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
                tier.update(self.travel.tips(destination, tier, trip.start_date, trip.end_date))
            tiers.append(tier)
        return {"destination": destination, "average_cents": avg, "budgets_counted": len(totals),
                "missing_budgets": missing, "tiers": tiers, "interests": interests or []}

    def create_poll(self, trip_id: str, question: str, options: list[str], closes_at: str | None = None) -> dict:
        trip = self._trip(trip_id)
        if len(options) < 2:
            raise ToolError("A poll needs at least 2 options")
        p = Poll(id=self._next_id("p", self._all_poll_ids()), question=question,
                 options=list(options), closes_at=closes_at)
        trip.polls.append(p)
        return {"poll_id": p.id, "options": p.options, "closes_at": closes_at}

    def vote_poll(self, poll_id: str, person_id: str, option: str) -> dict:
        trip, p = self._find_poll(poll_id)
        self._person(trip, person_id, active_only=True)
        if not p.is_open:
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
    def pairwise_debts(self, trip: Trip) -> dict[tuple[str, str], int]:
        """(debtor, creditor) -> cents, netted per pair only (never across the group)."""
        raw: dict[tuple[str, str], int] = {}
        for e in trip.expenses:
            refunded = self._refunded_by_person(trip, e.id)
            for p, share in e.splits.items():
                if p != e.paid_by:
                    raw[(p, e.paid_by)] = raw.get((p, e.paid_by), 0) + share - refunded.get(p, 0)
        net: dict[tuple[str, str], int] = {}
        for (a, b), amt in raw.items():
            if (b, a) in net or (a, b) in net:
                continue
            diff = amt - raw.get((b, a), 0)
            if diff > 0:
                net[(a, b)] = diff
            elif diff < 0:
                net[(b, a)] = -diff
        return net

    def get_balances(self, trip_id: str) -> dict:
        trip = self._trip(trip_id)
        out: dict[str, dict] = {}
        lines = []
        for (debtor, creditor), amt in sorted(self.pairwise_debts(trip).items()):
            out.setdefault(debtor, {"owes": []})["owes"].append({
                "to": creditor, "amount_cents": amt, "amount": rules.fmt_money(amt, trip.base_currency),
                "handle": trip.members[creditor].payment_handle})
            lines.append(_debt_line(trip, debtor, creditor, amt))
        # `lines` is chat-ready: quote it rather than re-deriving amounts or handles.
        return {"balances": out, "currency": trip.base_currency, "lines": lines}

    def _spent_by_category(self, trip: Trip, pid: str) -> dict[str, int]:
        spent: dict[str, int] = {}
        for e in trip.expenses:
            if e.category == "SETTLEMENT" or pid not in e.splits:
                continue
            share = e.splits[pid] - self._refunded_by_person(trip, e.id).get(pid, 0)
            spent[e.category] = spent.get(e.category, 0) + share
        return spent

    def _planned_by_category(self, trip: Trip, pid: str) -> dict[str, int]:
        planned = 0
        for a in trip.activities:
            if pid in a.attendees and a.expense_id is None and a.est_cost_cents \
                    and (a.start is None or a.start[:10] >= self.now[:10]):
                planned += self._activity_view(trip, a)["est_per_person_cents"]
        return {"ACTIVITIES": planned} if planned else {}

    def _upcoming(self, trip: Trip, pid: str) -> list[tuple[str, int]]:
        """(name, per-person cents) of this person's unpaid upcoming activities, priciest first."""
        items = [(a.name, self._activity_view(trip, a)["est_per_person_cents"]) for a in trip.activities
                 if pid in a.attendees and a.expense_id is None and a.est_cost_cents
                 and (a.start is None or a.start[:10] >= self.now[:10])]
        return sorted(items, key=lambda x: -x[1])

    def _flags(self, trip: Trip, pid: str) -> dict[str, str]:
        b = trip.budgets.get(pid)
        if b is None:
            return {}
        return rules.budget_flags(b.total_cents, b.limits, self._spent_by_category(trip, pid),
                                  self._planned_by_category(trip, pid),
                                  rules.trip_progress(trip.start_date, trip.end_date, self.now),
                                  self._upcoming(trip, pid), trip.base_currency)

    def _snapshot(self, trip: Trip, people) -> dict[str, dict[str, str]]:
        """Each person's warning flags before a change, to diff against afterwards."""
        return {pid: self._flags(trip, pid) for pid in people if pid in trip.budgets}

    def _budget_warnings(self, trip: Trip, before: dict[str, dict[str, str]]) -> dict[str, list[str]]:
        """Private: {person_id: messages} for warning lines this change newly crossed.
        Returned by the money-changing tools so the agent only has to DM, not check each person."""
        out = {}
        for pid, flags_before in before.items():
            new = rules.newly_crossed(flags_before, self._flags(trip, pid))
            if new:
                out[pid] = new
        return out

    def get_budget_status(self, trip_id: str, person_id: str) -> dict:
        trip = self._trip(trip_id)
        self._person(trip, person_id)
        b = trip.budgets.get(person_id)
        spent_by_cat = self._spent_by_category(trip, person_id)
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
            "warnings": rules.current_warnings(self._flags(trip, person_id)),
            "over_by_cents": max(spent - b.total_cents, 0),
            "upcoming": [{"name": n, "est_per_person": rules.fmt_money(c, trip.base_currency)}
                         for n, c in self._upcoming(trip, person_id)],
            "display": {k: rules.fmt_money(v, trip.base_currency) for k, v in {
                "total": b.total_cents, "spent": spent, "remaining": b.total_cents - spent,
                "planned": planned, "remaining_after_planned": b.total_cents - spent - planned}.items()},
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
        s["polls"] = [vars(p) for p in trip.polls]
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
                 "paid_by": e.paid_by, "amount_cents": e.amount_cents, "splits": e.splits}
                for e in trip.expenses[-10:]],
            "activities": [self._activity_view(trip, a) for a in trip.activities],
            "open_polls": [{"id": p.id, "question": p.question, "options": p.options,
                            "votes": len(p.votes)} for p in trip.polls if p.is_open],
        }
