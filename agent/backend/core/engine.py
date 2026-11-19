"""TripEngine: every backend tool, run on trip_model objects.

The data model and its rules (splits, refunds, balances, settle-up, opt-outs,
dropouts, polls, budget warnings) live in trip_model/. This module is the tool
layer on top: it turns tool arguments (ids, category names, ISO strings) into
model objects and model results back into JSON, makes ids, and holds the
trip-level tool rules (leader settings, the trip's plans and ideas list, the
agent's trip summary). Errors from the model come back to the agent as ToolErrors.

Trips live in memory here; DjangoBackend (backend/trips/services.py) loads a trip
from the database, runs the same engine on it and saves it back. It does NOT
enforce confirmations; whether the agent asked first is checked by the scenario
tests.
"""

import functools
import logging
import re
from datetime import date, datetime

from agent import config
from agent.backend.core import rules
from agent.backend.protocol import BACKEND_TOOLS, ToolError
from trip_model.activity import SLOTS, Activity
from trip_model.budget import Budget
from trip_model.category import Category
from trip_model.expense import Expense
from trip_model.money import split_proportional
from trip_model.person import Person
from trip_model.poll import Poll
from trip_model.reminder import Reminder
from trip_model.trip import Trip
from trip_model.trip_status import TripStatus

CATEGORIES = [c.name for c in Category]
STATUSES = [s.name for s in TripStatus]
# Decision types the group can route through the leader at onboarding (no default).
APPROVAL_TYPES = ["trip_changes", "member_changes", "refunds_deletes"]
TRIP_FIELDS = ["destination", "start_date", "end_date", "base_currency", "status",
               "target_break", "group_budget", "leader_id", "leader_approval", "name",
               "auto_log_mode", "lodging", "theme"]
# The trip page's looks: a beach or coast, a city, mountains or outdoors.
THEMES = ["sunset", "night_swim", "campfire"]

MAX_IDEAS = 20  # the ideas list stays short: things the group asked to keep, not a catalog
MAX_LODGING = 200

log = logging.getLogger(__name__)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "x"


# ----------------------------------------------------------- time at the edges
def parse_time(value: str, field: str) -> datetime:
    """ISO text -> naive datetime, so a timezone-aware "now" from Django compares with chat-entered times."""
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except (TypeError, ValueError) as e:
        raise ToolError(f"{field} must be ISO, like 2027-03-12T18:00") from e


def parse_day_or_time(value: str | None, field: str) -> date | datetime | None:
    """Activity times: a plain date ("2027-03-17") stays a date; anything else is a datetime."""
    if value is None:
        return None
    if isinstance(value, str) and "T" not in value and " " not in value:
        try:
            return date.fromisoformat(value)
        except ValueError as e:
            raise ToolError(f"{field} must be ISO, like 2027-03-15 or 2027-03-15T10:00") from e
    return parse_time(value, field)


def parse_day(value: str | None, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as e:
        raise ToolError(f"{field} must be an ISO date like 2027-03-16") from e


def iso(value: date | datetime | None) -> str | None:
    """Back to ISO text: seconds only when they aren't zero, like chat-entered times."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="minutes" if not value.second and not value.microsecond else "seconds")
    return value.isoformat()


def _day(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


class TripEngine:
    def __init__(self, now: str = "2027-03-01T12:00:00"):
        self.trips: dict[str, Trip] = {}
        self.now = now
        self._counters: dict[str, int] = {}

    # ------------------------------------------------------------------ helpers
    def _now(self) -> datetime:
        return parse_time(self.now, "now")

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
    def _category(name: str) -> Category:
        if name not in CATEGORIES:
            raise ToolError(f"Unknown category {name!r}. Use one of {CATEGORIES}")
        return Category[name]

    def _to_base(self, trip: Trip, amount: int, currency: str) -> tuple[int, float]:
        try:
            return rules.convert(amount, currency, trip.base_currency)
        except ValueError as e:
            raise ToolError(str(e)) from e

    @staticmethod
    def _split(amount: int, payer: Person, **how) -> dict[str, int]:
        """Net changes for an expense, worked out on a scratch Expense so a bad split changes nothing."""
        e = Expense(None, payer, amount, "", None)
        if "people" in how:
            return e.split_equal(how["people"])
        if "shares" in how:
            return e.split_custom(how["shares"])
        return e.split_percentage(how["percents"])

    def _compute_splits(self, trip: Trip, *, paid_by: str, amount: int, currency: str, category: str,
                        split_with: list[str] | None, exact_amounts: dict[str, int] | None,
                        percentages: dict[str, float] | None,
                        exclude: list[str] | None, override_opt_outs: list[str] | None):
        """Returns base amount, FX rate, category, net-change splits and auto-excluded people."""
        cat = self._category(category)
        if cat == Category.SETTLEMENT:
            raise ToolError("Paybacks go through record_payback, not log_expense")
        payer = trip.get_member(paid_by)
        if amount <= 0:
            raise ToolError("amount must be a positive number of cents")
        base_amount, rate = self._to_base(trip, amount, currency)
        auto_excluded = []
        if sum(x is not None for x in (split_with, exact_amounts, percentages)) != 1:
            raise ToolError("Pass exactly one of split_with, exact_amounts or percentages")
        if exact_amounts is not None:
            for pid in exact_amounts:
                trip.get_member(pid, active_only=True)
            if sum(exact_amounts.values()) != amount:
                raise ToolError(f"exact_amounts sum to {sum(exact_amounts.values())}, but amount is {amount}")
            shares = (dict(exact_amounts) if currency == trip.base_currency
                      else split_proportional(base_amount, exact_amounts))
            splits = self._split(base_amount, payer, shares=shares)
        elif percentages is not None:
            for pid in percentages:
                trip.get_member(pid, active_only=True)
            splits = self._split(base_amount, payer, percents=percentages)
        else:
            people, opted_out = trip.split_people(split_with, cat, exclude=set(exclude or []),
                                                  overrides=set(override_opt_outs or []))
            auto_excluded = [{"person_id": pid, "reason": f"opted out of {category}"} for pid in opted_out]
            splits = self._split(base_amount, payer, people=people)
        return base_amount, rate, cat, splits, auto_excluded

    # -------------------------------------------------------------------- views
    def _expense_view(self, e: Expense) -> dict:
        return {
            "expense_id": e.id, "description": e.description, "category": e.category.name,
            "paid_by": e.paid_by.id, "amount_cents": e.amount_cents,
            "original_amount": e.original_amount, "original_currency": e.original_currency,
            "fx_rate": e.fx_rate, "shares": e.shares(), "splits": e.splits,
            "created_at": iso(e.created_at), "refunded_cents": e.refunded_cents(),
        }

    @staticmethod
    def _activity_view(a: Activity) -> dict:
        return {"activity_id": a.id, "name": a.name, "location": a.location, "start": iso(a.start),
                "end": iso(a.end), "est_cost_cents": a.est_cost_cents,
                "cost_is_per_person": a.cost_is_per_person, "est_per_person_cents": a.est_per_person_cents(),
                "attendees": [p.id for p in a.attendees], "important": a.important,
                "booking_url": a.booking_url, "expense_id": a.expense_id,
                "slot": a.slot, "from_idea": a.from_idea}

    def _poll_view(self, p: Poll) -> dict:
        return {"id": p.id, "question": p.question, "options": p.options, "votes": p.votes,
                "closes_at": iso(p.closes_at), "is_open": p.check_open(self._now())}

    @staticmethod
    def _refund_view(r) -> dict:
        return {"id": r.id, "expense_id": r.expense_id, "amount_cents": r.amount_cents,
                "original_amount": r.original_amount, "currency": r.currency, "note": r.note,
                "per_person": r.per_person, "created_at": iso(r.created_at)}

    @staticmethod
    def _reminder_view(r: Reminder) -> dict:
        audience = r.audience if r.audience == "all" else [p.id for p in r.audience]
        return {"id": r.id, "message": r.message, "due_at": iso(r.due_at), "audience": audience,
                "sent": r.sent, "created_by": r.created_by}

    @staticmethod
    def _activities_outside(trip: Trip) -> list[str]:
        if not (trip.start_date and trip.end_date):
            return []
        return [a.id for a in trip.activities
                if a.start and not (trip.start_date <= _day(a.start) <= trip.end_date)]

    # ------------------------------------------------------------------ seeding
    def load_seed(self, seed: dict) -> None:
        """Build a trip from a scenario 'seed' block (see tests/scenarios/*.yaml)."""
        if "now" in seed:
            self.now = str(seed["now"])
        t = seed["trip"]
        fields = {k: t[k] for k in TRIP_FIELDS if k in t and k != "name"}
        if "status" in fields:
            fields["status"] = TripStatus[fields["status"]]
        for k in ("start_date", "end_date"):
            if k in fields:
                fields[k] = parse_day(str(fields[k]), k)
        trip = Trip(id=t["id"], name=t.get("name", t["id"]), share_token=t.get("share_token"), **fields)
        if "leader" in t:
            trip.leader_id = t["leader"]
        self.trips[trip.id] = trip
        for m in seed.get("members", []):
            trip.add_member(Person(m["id"], m["name"], m.get("chat_user_id", m["id"]), m.get("handle"),
                                   active=m.get("active", True)))
        for pid, b in (seed.get("budgets") or {}).items():
            trip.get_member(pid).budget = Budget(pid, b["total"], {Category[c]: v for c, v in b.get("limits", {}).items()})
        for pid, cat in seed.get("exclusions", []):
            trip.set_opt_out(pid, Category[cat])
        for e in seed.get("expenses", []):
            self.log_expense(trip_id=trip.id, paid_by=e["paid_by"], amount=e["amount"],
                             currency=e.get("currency", trip.base_currency),
                             description=e["description"], category=e["category"],
                             split_with=e["split_with"])
            if "id" in e:
                trip.expenses[-1].id = e["id"]
        for idea in seed.get("ideas", []):
            self.save_idea(trip_id=trip.id, **idea)
        for pb in seed.get("paybacks", []):
            self.record_payback(trip_id=trip.id, from_person=pb["from"], to_person=pb["to"],
                                amount=pb["amount"], currency=trip.base_currency)
            if "id" in pb:
                trip.expenses[-1].id = pb["id"]
        for a in seed.get("activities", []):
            a = dict(a)
            attendees = a.pop("attendees", trip.active_member_ids())
            trip.add_activity(Activity(
                **a | {"start": parse_day_or_time(a.get("start"), "start"),
                       "end": parse_day_or_time(a.get("end"), "end")},
                attendees=[trip.get_member(pid) for pid in attendees]))
        for p in seed.get("polls", []):
            p = dict(p)
            if p.get("closes_at"):
                p["closes_at"] = parse_time(p["closes_at"], "closes_at")
            trip.add_poll(Poll(**p))

    # ================================================================= TOOLS
    # ---------------------------------------------------------------- expenses
    def log_expense(self, trip_id: str, paid_by: str, amount: int, currency: str, description: str,
                    category: str, split_with: list[str] | None = None,
                    exact_amounts: dict[str, int] | None = None,
                    percentages: dict[str, float] | None = None, exclude: list[str] | None = None,
                    override_opt_outs: list[str] | None = None, source_message: str = "") -> dict:
        trip = self._trip(trip_id)
        base_amount, rate, cat, splits, auto_excluded = self._compute_splits(
            trip, paid_by=paid_by, amount=amount, currency=currency, category=category,
            split_with=split_with, exact_amounts=exact_amounts, percentages=percentages,
            exclude=exclude, override_opt_outs=override_opt_outs)
        e = Expense(self._next_id("e", self._all_expense_ids()), trip.get_member(paid_by), base_amount,
                    description, cat, splits=splits, created_at=self._now(), source_message=source_message,
                    original_amount=amount, original_currency=currency, fx_rate=rate)
        trip.add_expense(e)
        return {"expense_id": e.id, "base_amount": base_amount, "base_currency": trip.base_currency,
                "original_amount": amount, "original_currency": currency, "fx_rate": rate,
                "shares": e.shares(), "splits": splits, "auto_excluded": auto_excluded}

    def edit_expense(self, expense_id: str, requested_by: str, changes: dict) -> dict:
        trip, e = self._find_expense(expense_id)
        trip.get_member(requested_by)
        if e.category == Category.SETTLEMENT:
            raise ToolError("That's a payback, not an expense; delete it and record the payback again")
        allowed = {"amount", "currency", "description", "category", "split_with", "exact_amounts",
                   "percentages", "exclude", "override_opt_outs", "paid_by"}
        bad = set(changes) - allowed
        if bad:
            raise ToolError(f"Can't change {sorted(bad)}; allowed: {sorted(allowed)}")
        money_keys = allowed - {"description"}
        if money_keys & set(changes):
            split_with = changes.get("split_with")
            exact = changes.get("exact_amounts")
            percentages = changes.get("percentages")
            if split_with is None and exact is None and percentages is None:
                split_with = list(e.shares())  # keep the same people
            amount = changes.get("amount", e.original_amount)
            currency = changes.get("currency", e.original_currency)
            paid_by = changes.get("paid_by", e.paid_by.id)
            base_amount, rate, cat, splits, _ = self._compute_splits(
                trip, paid_by=paid_by, amount=amount, currency=currency,
                category=changes.get("category", e.category.name),
                split_with=split_with, exact_amounts=exact, percentages=percentages,
                exclude=changes.get("exclude"), override_opt_outs=changes.get("override_opt_outs"))
            e.amount_cents, e.fx_rate, e.splits, e.category = base_amount, rate, splits, cat
            e.original_amount, e.original_currency, e.paid_by = amount, currency, trip.get_member(paid_by)
        if "description" in changes:
            e.description = changes["description"]
        return {"updated": True, "payer": e.paid_by.id, "expense": self._expense_view(e)}

    def delete_expense(self, expense_id: str, requested_by: str) -> dict:
        trip, e = self._find_expense(expense_id)
        trip.get_member(requested_by)
        trip.delete_expense(expense_id)
        return {"deleted": True, "expense_id": expense_id, "payer": e.paid_by.id}

    def record_refund(self, expense_id: str, amount: int, currency: str, note: str = "") -> dict:
        trip, e = self._find_expense(expense_id)
        base, _ = self._to_base(trip, amount, currency)
        r = trip.add_refund(expense_id, self._next_id("r", {r.id for r in trip.refunds}), base, note=note,
                            created_at=self._now(), original_amount=amount, currency=currency)
        return {"refund_id": r.id, "expense_id": expense_id, "payer": e.paid_by.id,
                "base_amount": base, "per_person": r.per_person}

    def record_payback(self, trip_id: str, from_person: str, to_person: str, amount: int,
                       currency: str) -> dict:
        trip = self._trip(trip_id)
        base, rate = self._to_base(trip, amount, currency)
        e = trip.record_settlement(from_person, to_person, base, self._next_id("e", self._all_expense_ids()),
                                   created_at=self._now())
        e.original_amount, e.original_currency, e.fx_rate = amount, currency, rate
        return {"expense_id": e.id, "from": from_person, "to": to_person, "base_amount": base,
                "base_currency": trip.base_currency, "original_amount": amount,
                "original_currency": currency}

    # ---------------------------------------------------------- trip & members
    def add_member(self, trip_id: str, chat_user_id: str, name: str, payment_handle: str | None = None) -> dict:
        trip = self._trip(trip_id)
        for p in trip.members:
            if p.chat_user_id == chat_user_id:
                p.active = True
                p.name = name or p.name
                p.payment_handle = payment_handle or p.payment_handle
                return {"person_id": p.id, "added": True, "rejoined": True}
        pid = _slug(name)
        while pid in trip.member_ids():
            pid += "_2"
        trip.add_member(Person(pid, name, chat_user_id, payment_handle))
        return {"person_id": pid, "added": True, "rejoined": False}

    def remove_member(self, trip_id: str, person_id: str) -> dict:
        trip = self._trip(trip_id)
        removed_from = trip.remove_member(person_id)
        return {"removed": True, "removed_from_activities": removed_from,
                "still_owes_past_splits": True, "was_leader": trip.leader_id == person_id}

    @staticmethod
    def _lodging(value) -> str | None:
        """Where the group is staying, saved as they wrote it (a hotel name or an address). Empty clears it."""
        if value is None:
            return None
        if not isinstance(value, str) or len(value.strip()) > MAX_LODGING:
            raise ToolError(f"lodging must be a hotel name or address, up to {MAX_LODGING} characters")
        return value.strip() or None

    def update_trip(self, trip_id: str, changes: dict) -> dict:
        trip = self._trip(trip_id)
        bad = set(changes) - set(TRIP_FIELDS)
        if bad:
            raise ToolError(f"Can't change {sorted(bad)}; allowed: {TRIP_FIELDS}")
        new = dict(changes)
        if "status" in new:
            if new["status"] not in STATUSES:
                raise ToolError(f"status must be one of {STATUSES}")
            new["status"] = TripStatus[new["status"]]
        if "leader_id" in new:
            trip.get_member(new["leader_id"], active_only=True)
        if "leader_approval" in new:
            bad = set(new["leader_approval"]) - set(APPROVAL_TYPES)
            if bad:
                raise ToolError(f"Unknown leader_approval types {sorted(bad)}; use {APPROVAL_TYPES}")
        if "lodging" in new:
            new["lodging"] = self._lodging(new["lodging"])
        if "base_currency" in new and new["base_currency"] != trip.base_currency:
            if new["base_currency"] not in rules.USD_PER_UNIT:
                raise ToolError(f"Unsupported currency {new['base_currency']!r}")
            if trip.expenses:
                raise ToolError("Can't change base_currency after expenses are logged")
        for k in ("start_date", "end_date"):
            if k in new:
                new[k] = parse_day(new[k], k)
        new_start = new.get("start_date", trip.start_date)
        new_end = new.get("end_date", trip.end_date)
        if new_start and new_end and new_start > new_end:
            raise ToolError("start_date is after end_date")
        theme_kept = None
        if "theme" in new:
            if new["theme"] not in THEMES:
                raise ToolError(f"theme must be one of {THEMES}")
            if trip.theme_set_by == "member":  # picked on the trip page: the bot doesn't change it
                theme_kept = trip.theme
                del new["theme"]
            else:
                new["theme_set_by"] = "bot"
        for k, v in new.items():
            setattr(trip, k, v)
        out = {"updated": True, "trip": self.summary(trip_id)["trip"]}
        if theme_kept:
            out["theme_kept"] = f"Someone picked the {theme_kept} theme on the trip page, so it stays. No need to mention it."
        if "start_date" in changes or "end_date" in changes:
            out["activities_outside_dates"] = self._activities_outside(trip)
        if "group_budget" in changes and changes["group_budget"] is not None:
            # Budgets are shared with the trip, so the agent can name these people in the group.
            out["members_below_group_budget"] = sorted(
                p.id for p in trip.members
                if p.active and p.budget and p.budget.total_cents < changes["group_budget"])
            out["members_without_budget"] = sorted(
                p.id for p in trip.members if p.active and p.budget is None)
        return out

    def set_budget(self, trip_id: str, person_id: str, total: int, limits: dict[str, int] | None = None) -> dict:
        trip = self._trip(trip_id)
        person = trip.get_member(person_id)
        if total < 0:
            raise ToolError("total must be >= 0 cents")
        person.budget = Budget(person_id, total, {self._category(c): v for c, v in (limits or {}).items()})
        return {"saved": True, "person_id": person_id, "total_cents": total, "limits": limits or {}}

    def set_exclusion(self, trip_id: str, person_id: str, category: str, remove: bool = False) -> dict:
        trip = self._trip(trip_id)
        cat = self._category(category)
        if remove:
            trip.remove_opt_out(person_id, cat)
        else:
            trip.set_opt_out(person_id, cat)
        return {"saved": True, "person_id": person_id, "category": category, "opted_out": not remove}

    # ---------------------------------------------------------------- planning
    # The bot keeps track of what the group decides. It doesn't suggest places or check them anywhere (Nov 12, 2026).
    @staticmethod
    def _same_time(trip: Trip, start, skip: Activity | None = None) -> list[str]:
        """Other plans at exactly this clock time. Plans in a slot or with just a day never clash."""
        if not isinstance(start, datetime):
            return []
        return [a.name for a in trip.activities if a is not skip and isinstance(a.start, datetime) and a.start == start]

    @staticmethod
    def _moved(a: Activity, on: date) -> dict:
        """Moving a plan to another day keeps its clock time or slot (and how long it lasts)."""
        shift = on - _day(a.start) if a.start else None
        if a.start is None:
            return {"start": on}
        start = datetime.combine(on, a.start.time()) if isinstance(a.start, datetime) else on
        return {"start": start, "end": a.end + shift if a.end is not None else None}

    def add_activity(self, trip_id: str, name: str | None = None, activity_id: str | None = None,
                     location: str | None = None, start: str | None = None, end: str | None = None,
                     est_cost_cents: int | None = None, cost_is_per_person: bool | None = None,
                     attendees: list[str] | None = None, important: bool | None = None,
                     booking_url: str | None = None, expense_id: str | None = None, day: str | None = None,
                     slot: str | None = None, idea_id: str | None = None, confirm_same_time: bool = False) -> dict:
        trip = self._trip(trip_id)
        people = None if attendees is None else [trip.get_member(pid, active_only=True) for pid in attendees]
        fields = {"name": name, "location": location, "start": parse_day_or_time(start, "start"),
                  "end": parse_day_or_time(end, "end"), "est_cost_cents": est_cost_cents,
                  "cost_is_per_person": cost_is_per_person, "attendees": people, "important": important,
                  "booking_url": booking_url, "expense_id": expense_id}
        fields = {k: v for k, v in fields.items() if v is not None}
        if slot is not None and slot not in SLOTS:
            raise ToolError(f"slot must be one of {list(SLOTS)}")
        if slot and isinstance(fields.get("start"), datetime):
            raise ToolError("Pass a slot or a clock time in start, not both")
        on = parse_day(day, "day")
        match = None
        if activity_id:
            match = next((a for a in trip.activities if a.id == activity_id), None)
            if match is None:
                raise ToolError(f"No activity {activity_id!r}")
            if on and "start" not in fields:
                fields.update(self._moved(match, on))
        elif on and "start" not in fields:
            fields["start"] = on  # just the day, unless they named a slot
        if slot:
            day_of = fields.get("start", match.start if match else None)
            if day_of is None:
                raise ToolError("A slot needs a day: pass day too")
            fields.update(start=_day(day_of), end=None, slot=slot)
        elif isinstance(fields.get("start"), datetime):
            fields["slot"] = None  # a clock time replaces a slot
        in_slot = fields.get("slot") or (match is not None and match.slot and "start" not in fields)
        if in_slot and isinstance(fields.get("end"), datetime):
            raise ToolError("A plan in a slot (like lunch) has no clock times. To give it an end time, pass a clock "
                            "start time too, which replaces the slot.")
        clash = self._same_time(trip, fields.get("start"), skip=match)
        if clash and not confirm_same_time:  # nothing saved until the person says yes
            return {"created" if not match else "updated": False, "same_time_as": clash,
                    "at": iso(fields["start"]),
                    "next_step": "Ask the person if they really want both at that time. If they say yes, call again "
                                 "with confirm_same_time: true."}
        if match:
            match.update(**fields)
            return {"activity_id": activity_id, "updated": True, "start": iso(match.start), "end": iso(match.end),
                    "slot": match.slot, "outside_trip_dates": match.id in self._activities_outside(trip)}
        idea = None
        if idea_id:
            idea = next((i for i in trip.ideas if i["idea_id"] == idea_id), None)
            if idea is None:
                raise ToolError(f"No idea {idea_id!r}")
            fields.setdefault("name", idea["name"])
            if idea.get("location"):  # ideas saved before the planning cut can have one
                fields.setdefault("location", idea["location"])
            if idea.get("est_cost_cents") is not None:
                fields.setdefault("est_cost_cents", idea["est_cost_cents"])
        if not str(fields.get("name") or "").strip():
            raise ToolError("name is required for a new activity")
        fields["name"] = fields["name"].strip()
        fields.setdefault("attendees", [p for p in trip.members if p.active])
        a = Activity(self._next_id("a", {a.id for a in trip.activities}), **fields, from_idea=bool(idea))
        trip.add_activity(a)
        if idea:
            trip.ideas.remove(idea)
        return {"activity_id": a.id, "created": True, "start": iso(a.start), "end": iso(a.end), "slot": a.slot,
                "outside_trip_dates": a.id in self._activities_outside(trip), "from_ideas": bool(idea)}

    def remove_activity(self, trip_id: str, activity_id: str) -> dict:
        trip = self._trip(trip_id)
        a = trip.remove_activity(activity_id)
        back = (a.from_idea and len(trip.ideas) < MAX_IDEAS
                and a.name.lower() not in {i["name"].lower() for i in trip.ideas})
        if back:  # it came off the ideas list, so it goes back on
            trip.ideas.append({"idea_id": self._next_id("i", {i["idea_id"] for i in trip.ideas}), "name": a.name,
                               "est_cost_cents": a.est_per_person_cents(), "suggested_by": None})
        return {"removed": True, "activity_id": a.id, "name": a.name, "back_on_ideas": back,
                "expense_still_logged": a.expense_id}

    def save_idea(self, trip_id: str, name: str | None = None, est_cost_cents: int | None = None,
                  idea_id: str | None = None, remove: bool = False, suggested_by: str | None = None) -> dict:
        trip = self._trip(trip_id)
        if remove:  # anyone on the trip can drop an idea
            key = (name or "").strip().lower()
            match = next((i for i in trip.ideas if i["idea_id"] == idea_id or (key and i["name"].lower() == key)),
                         None)
            if match is None:
                raise ToolError(f"No idea {idea_id or name!r}. Ideas: {[i['name'] for i in trip.ideas]}")
            trip.ideas.remove(match)
            return {"removed": True, "name": match["name"], "ideas_left": len(trip.ideas)}
        if not (name or "").strip():
            raise ToolError("An idea needs a name")
        if est_cost_cents is not None and (isinstance(est_cost_cents, bool) or not isinstance(est_cost_cents, int)
                                           or est_cost_cents < 0):
            raise ToolError("est_cost_cents must be whole cents, 0 or more ($25 -> 2500)")
        same = next((i for i in trip.ideas if i["name"].lower() == name.strip().lower()), None)
        if same:
            return {"saved": False, "already_on_list": True, "idea": same}
        if len(trip.ideas) >= MAX_IDEAS:
            raise ToolError(f"The ideas list is full ({MAX_IDEAS}). Put some on a day or drop some first.")
        if suggested_by:
            trip.get_member(suggested_by)
        idea = {"idea_id": self._next_id("i", {i["idea_id"] for i in trip.ideas}), "name": name.strip(),
                "est_cost_cents": est_cost_cents, "suggested_by": suggested_by}
        trip.ideas.append(idea)
        return {"saved": True, "idea": idea, "ideas_count": len(trip.ideas)}

    def create_poll(self, trip_id: str, question: str, options: list[str], closes_at: str | None = None) -> dict:
        trip = self._trip(trip_id)
        if len(options) < 2:
            raise ToolError("A poll needs at least 2 options")
        p = Poll(self._next_id("p", self._all_poll_ids()), question, list(options),
                 closes_at=None if closes_at is None else parse_time(closes_at, "closes_at"))
        trip.add_poll(p)
        return {"poll_id": p.id, "options": p.options, "closes_at": closes_at}

    def vote_poll(self, poll_id: str, person_id: str, option: str) -> dict:
        trip, p = self._find_poll(poll_id)
        trip.get_member(person_id, active_only=True)
        p.vote(person_id, option, now=self._now())
        return {"recorded": True, "votes_so_far": len(p.votes), "voters_left": [
            m for m in trip.active_member_ids() if m not in p.votes]}

    def close_poll(self, poll_id: str) -> dict:
        _, p = self._find_poll(poll_id)
        p.close()
        leaders = p.winner()
        return {"poll_id": p.id, "question": p.question, "counts": p.results(),
                "winner": leaders[0] if len(leaders) == 1 else None,
                "tie": leaders if len(leaders) > 1 else []}

    def create_reminder(self, trip_id: str, message: str, due_at: str, audience: list[str] | str) -> dict:
        trip = self._trip(trip_id)
        if audience in ("all", ["all"]):
            audience = "all"
            people = "all"
        else:
            people = [trip.get_member(pid) for pid in audience]
        r = Reminder(message, parse_time(due_at, "due_at"), people, created_by="agent",
                     id=self._next_id("m", {r.id for r in trip.reminders}))
        trip.add_reminder(r)
        return {"reminder_id": r.id, "due_at": due_at, "audience": audience}

    # ------------------------------------------------------ money info & reads
    def settle_up(self, trip: Trip) -> dict[tuple[str, str], int]:
        """(from, to) -> cents: the suggested payments, netted across the group."""
        return {(d, c): amt for d, c, amt in trip.settlement_plan()}

    def get_balances(self, trip_id: str) -> dict:
        trip = self._trip(trip_id)
        return {
            "net_balances": {pid: c for pid, c in trip.balances().items() if c},
            "suggested_payments": [
                {"from": d, "to": c, "amount_cents": amt, "handle": trip.get_member(c).payment_handle}
                for d, c, amt in trip.settlement_plan()],
            "currency": trip.base_currency,
        }

    def _planned_by_category(self, trip: Trip, person: Person) -> dict[str, int]:
        planned = 0
        today = self._now().date()
        for a in trip.activities:
            if person in a.attendees and a.expense_id is None and a.est_cost_cents \
                    and (a.start is None or _day(a.start) >= today):
                planned += a.est_per_person_cents()
        return {"ACTIVITIES": planned} if planned else {}

    @staticmethod
    def _budget_warnings(trip: Trip, b: Budget, planned_by_cat: dict[str, int]) -> list[str]:
        """Category limits only: a warning once under 10% of a limit is left, counting planned activities."""
        warnings = []
        for cat in sorted(b.limits, key=lambda c: c.name):
            planned = planned_by_cat.get(cat.name, 0)
            left = b.remaining(cat, trip.expenses) - planned
            if left < 0:
                warnings.append(f"{cat.name} over limit by {rules.fmt_usd(-left)} including planned activities")
            elif b.warning(cat, trip.expenses, planned):
                warnings.append(f"{cat.name} under 10% remaining")
        return warnings

    def get_budget_status(self, trip_id: str, person_id: str) -> dict:
        trip = self._trip(trip_id)
        person = trip.get_member(person_id)
        b = person.budget
        spent_by_cat = {c.name: v for c, v in trip.spent_by_category(person).items() if v}
        planned_by_cat = self._planned_by_category(trip, person)
        spent, planned = sum(spent_by_cat.values()), sum(planned_by_cat.values())
        if b is None:
            return {"person_id": person_id, "budget_set": False, "spent_cents": spent,
                    "planned_cents": planned, "warnings": []}
        limits = {c.name: v for c, v in b.limits.items()}
        cats = sorted(set(limits) | set(spent_by_cat) | set(planned_by_cat))
        return {
            "person_id": person_id, "budget_set": True,
            "total_cents": b.total_cents, "spent_cents": spent,
            "remaining_cents": b.total_cents - spent, "planned_cents": planned,
            "remaining_after_planned_cents": b.total_cents - spent - planned,
            "by_category": {c: {"limit_cents": limits.get(c), "spent_cents": spent_by_cat.get(c, 0),
                                "planned_cents": planned_by_cat.get(c, 0)} for c in cats},
            "warnings": self._budget_warnings(trip, b, planned_by_cat),
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
        s["expenses"] = [self._expense_view(e) for e in trip.expenses]
        s["refunds"] = [self._refund_view(r) for r in trip.refunds]
        s["polls"] = [self._poll_view(p) for p in trip.polls]
        s["reminders"] = [self._reminder_view(r) for r in trip.reminders]
        s["ideas"] = trip.ideas
        # Budgets are shared with everyone on the trip (decided Oct 28, 2026).
        s["budgets"] = {p.id: {"total_cents": p.budget.total_cents,
                               "limits": {c.name: v for c, v in p.budget.limits.items()}}
                        for p in trip.members if p.budget}
        return s

    # ------------------------------------------------------------- not a tool
    def set_theme(self, trip_id: str, theme: str) -> dict:
        """A member picked the trip page's look on the page. Not a tool: the bot sets it through update_trip,
        and only until a member picks one."""
        if theme not in THEMES:
            raise ToolError(f"theme must be one of {THEMES}")
        trip = self._trip(trip_id)
        trip.theme, trip.theme_set_by = theme, "member"
        return {"theme": theme}

    def budget_overview(self, trip_id: str) -> dict:
        """Everyone's budget status, by person id: for the trip page's Budgets card."""
        trip = self._trip(trip_id)
        return {p.id: self.get_budget_status(trip_id=trip_id, person_id=p.id) for p in trip.members if p.active}

    def summary(self, trip_id: str) -> dict:
        trip = self._trip(trip_id)
        now = self._now()
        return {
            "trip": {"id": trip.id, "name": trip.name, "status": trip.status.name,
                     "destination": trip.destination, "start_date": iso(trip.start_date),
                     "end_date": iso(trip.end_date), "target_break": trip.target_break,
                     "base_currency": trip.base_currency, "group_budget_cents": trip.group_budget,
                     "leader_id": trip.leader_id, "leader_approval": sorted(trip.leader_approval),
                     "auto_log_mode": trip.auto_log_mode, "lodging": trip.lodging, "theme": trip.theme,
                     # The trip page, for "what's the link?". None until the database gives the trip a token.
                     "page_url": f"{config.TRIP_PAGE_URL}/t/{trip.share_token}" if trip.share_token else None},
            "members": [{"id": p.id, "name": p.name, "handle": p.payment_handle,
                         "active": p.active, "budget_set": p.budget is not None,
                         "budget_cents": p.budget.total_cents if p.budget else None}
                        for p in trip.members],
            "category_opt_outs": sorted([pid, cat.name] for pid, cat in trip.opt_outs),
            "recent_expenses": [
                {"id": e.id, "description": e.description, "category": e.category.name,
                 "paid_by": e.paid_by.id, "amount_cents": e.amount_cents, "shares": e.shares()}
                for e in trip.expenses[-10:]],
            "activities": [self._activity_view(a) for a in trip.activities],
            "ideas": [{"idea_id": i["idea_id"], "name": i["name"]} for i in trip.ideas],
            "open_polls": [{"id": p.id, "question": p.question, "options": p.options,
                            "votes": len(p.votes)} for p in trip.polls if p.check_open(now)],
        }


def _model_errors_as_tool_errors(method):
    """trip_model raises ValueError for rule violations; the agent sees them as tool errors."""
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ValueError as e:
            raise ToolError(str(e)) from e
    return wrapper


for _name in BACKEND_TOOLS:
    setattr(TripEngine, _name, _model_errors_as_tool_errors(getattr(TripEngine, _name)))
