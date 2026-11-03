"""TripEngine: every backend tool, run on trip_model objects.

The data model and its rules (splits, refunds, balances, settle-up, opt-outs,
dropouts, polls, budget warnings) live in trip_model/. This module is the tool
layer on top: it turns tool arguments (ids, category names, ISO strings) into
model objects and model results back into JSON, makes ids, and holds the
trip-level tool rules (leader settings, travel tips, itinerary drafts, the agent's
trip summary). Errors from the model come back to the agent as ToolErrors.

Trips live in memory here; DjangoBackend (backend/trips/services.py) loads a trip
from the database, runs the same engine on it and saves it back. It does NOT
enforce confirmations; whether the agent asked first is checked by the scenario
tests.
"""

import functools
import logging
import re
from datetime import date, datetime, time, timedelta

from agent.backend.core import rules
from agent.backend.protocol import BACKEND_TOOLS, ToolError
from agent.travel import nearby, osm, planner
from agent.travel.planner import KINDS, pick_slot, plan_days, taken
from agent.travel.provider import get_provider
from trip_model.activity import Activity, as_datetime
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
APPROVAL_TYPES = ["trip_changes", "member_changes", "itinerary_saves", "refunds_deletes"]
TRIP_FIELDS = ["destination", "start_date", "end_date", "base_currency", "status",
               "target_break", "group_budget", "leader_id", "leader_approval", "name",
               "auto_log_mode", "planning_notes", "lodging"]

# Itinerary drafts: each suggested stop is checked on the map (about a second each), so a draft is capped.
MAX_STOPS_PER_DAY = 3
MAX_STOPS = 15
MAX_IDEAS = 20  # the ideas list stays short: places the group asked to keep, not a catalog
MAX_NOTES = 500
NEARBY_RADIUS_M = 1600  # about a mile, about a 20-minute walk
MAX_RADIUS_M = 5000     # about 3 miles
MAX_NEARBY = 5
NEARBY_NOTE = "Closest first (OpenStreetMap has no ratings). Straight-line distances; walking times are rough."
ESTIMATES_NOTE = "Hours and prices are estimates; check before you go."

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


def _hours(stop: dict) -> dict | None:
    """A checked stop's parsed opening hours (stored as the raw OpenStreetMap text, which survives JSON)."""
    return osm.parse_opening_hours(stop["opening_hours"]) if stop.get("opening_hours") else None


def _at(day: date, minutes: int) -> datetime:
    return datetime.combine(day, time()) + timedelta(minutes=minutes)


class TripEngine:
    def __init__(self, now: str = "2027-03-01T12:00:00", travel=None):
        # Romir's hook: where travel tips/itinerary ideas come from. Live Google Places + SerpAPI when
        # their keys are set, canned otherwise (agent/travel/provider.py).
        self.travel = travel or get_provider()
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
                "lat": a.lat, "lon": a.lon, "verified": a.verified, "kind": a.kind, "from_idea": a.from_idea}

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
        fields = {k: t[k] for k in TRIP_FIELDS if k in t and k not in ("name", "lodging")}
        if "status" in fields:
            fields["status"] = TripStatus[fields["status"]]
        for k in ("start_date", "end_date"):
            if k in fields:
                fields[k] = parse_day(str(fields[k]), k)
        trip = Trip(id=t["id"], name=t.get("name", t["id"]), **fields)
        if "leader" in t:
            trip.leader_id = t["leader"]
        self.trips[trip.id] = trip
        if t.get("lodging"):  # looked up on the map like one set from chat
            self.update_trip(trip.id, {"lodging": t["lodging"]})
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

    def _find_lodging(self, name, city: str | None) -> dict | None:
        """Where the group is staying, looked up on the map near the destination. Empty clears it. Nothing is saved
        if the map can't find it, so the agent asks for the street address."""
        if name is None or not str(name).strip():
            return None
        name = str(name).strip()
        if not city:
            raise ToolError("Set the destination first, so the place can be found on the map")
        try:
            found = self.travel.find_place(name, city)
        except Exception as e:  # noqa: BLE001
            log.warning("Lodging lookup failed for %r in %s: %s", name, city, e)
            raise ToolError("The map lookup failed, so nothing was saved. Try again in a minute.") from e
        if found is None:
            raise ToolError(f"Couldn't find {name!r} on the map near {city}, so nothing was saved. "
                            'Ask for the street address (e.g. "2727 Indian Creek Dr").')
        return {"name": name, "address": osm.short_address(found), "lat": found.lat, "lon": found.lon,
                "maps_url": found.maps_url}

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
        if "planning_notes" in new and new["planning_notes"] is not None:
            if not isinstance(new["planning_notes"], str) or len(new["planning_notes"]) > MAX_NOTES:
                raise ToolError(f"planning_notes must be text, up to {MAX_NOTES} characters")
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
        if "lodging" in new:  # last, so a lodging the map can't find leaves the whole change unsaved
            new["lodging"] = self._find_lodging(new["lodging"], new.get("destination", trip.destination))
        for k, v in new.items():
            setattr(trip, k, v)
        out = {"updated": True, "trip": self.summary(trip_id)["trip"]}
        if new.get("lodging"):
            out["next_step"] = ("Tell the group the address you saved, with the Maps link, so someone can correct it "
                                "if it's the wrong place.")
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
    def generate_itinerary(self, trip_id: str, places: list[dict] | None = None, days: list[str] | None = None,
                           use_ideas: bool = True, constraints: str | None = None,
                           save_draft_id: str | None = None) -> dict:
        trip = self._trip(trip_id)
        if save_draft_id:
            if save_draft_id not in trip.itinerary_drafts:
                raise ToolError(f"No draft {save_draft_id!r}")
            ids, already = [], []
            on_trip = {(a.name.lower(), iso(a.start)) for a in trip.activities}
            draft = trip.itinerary_drafts.pop(save_draft_id)
            for day in draft:
                for item in day["items"]:
                    if (item["name"].lower(), item["start"]) in on_trip:  # saved from an earlier draft
                        already.append(item["name"])
                        continue
                    a = Activity(self._next_id("a", {a.id for a in trip.activities}), item["name"],
                                 location=item["location"], start=parse_day_or_time(item["start"], "start"),
                                 end=parse_day_or_time(item["end"], "end"),
                                 est_cost_cents=item["est_cost_cents"],
                                 cost_is_per_person=item["cost_is_per_person"],
                                 attendees=[p for p in trip.members if p.active],
                                 lat=item.get("lat"), lon=item.get("lon"), verified=item.get("verified"),
                                 kind=item.get("kind"), from_idea=bool(item.get("idea_id")))
                    trip.add_activity(a)
                    ids.append(a.id)
            # Ideas that made it onto a day leave the ideas list.
            used = {item["idea_id"] for day in draft for item in day["items"] if item.get("idea_id")}
            scheduled = [i["name"] for i in trip.ideas if i["idea_id"] in used]
            trip.ideas = [i for i in trip.ideas if i["idea_id"] not in used]
            return {"saved": True, "activity_ids": ids, "already_on_trip": already, "ideas_scheduled": scheduled}
        if not (trip.destination and trip.start_date and trip.end_date):
            raise ToolError("Set destination, start_date and end_date before generating an itinerary")
        dates = self._plan_dates(trip, days)
        ideas = trip.ideas if use_ideas else []
        if places or ideas:
            plan, extra = self._draft_from_places(trip, places or [], dates, ideas)
        elif self.travel.source == "live":  # Google Places picks the stops (only when its key is set)
            plan, extra = self._draft_from_provider(trip, dates, constraints), {}
        else:
            raise ToolError(f"Pass places: the stops you suggest, up to {MAX_STOPS_PER_DAY} a day, each with name, "
                            "kind (food, activity or night) and est_cost_cents per person")
        # One draft at a time: a rebuilt draft replaces the old one, so an old draft_id can't save a stale plan.
        replaced = sorted(trip.itinerary_drafts)
        draft_id = self._next_id("d", set(replaced))
        trip.itinerary_drafts = {draft_id: plan}
        return {"draft_id": draft_id, "days": plan, "constraints": constraints, "source": self.travel.source,
                "saved": False, "replaced_drafts": replaced, **extra}

    @staticmethod
    def _check_place_arg(p) -> None:
        if not isinstance(p, dict) or not str(p.get("name") or "").strip() or p.get("kind") not in KINDS:
            raise ToolError("Each place needs a name and a kind: food, activity or night")
        cost = p.get("est_cost_cents")
        if cost is not None and (isinstance(cost, bool) or not isinstance(cost, int) or cost < 0):
            raise ToolError(f"est_cost_cents for {p['name']!r} must be whole cents, 0 or more ($25 -> 2500)")

    @staticmethod
    def _draft_item(it: dict, day: date) -> dict:
        """A planned stop (with slot, start_min, end_min, hours_conflict) as it's stored in a draft."""
        return {"name": it["name"], "kind": it["kind"], "slot": it["slot"], "location": it["location"],
                "start": iso(_at(day, it["start_min"])), "end": iso(_at(day, it["end_min"])),
                "est_cost_cents": it.get("est_cost_cents"), "cost_is_per_person": True, "verified": it["verified"],
                "lat": it["lat"], "lon": it["lon"], "opening_hours": it["opening_hours"],
                "hours_conflict": it["hours_conflict"], "maps_url": it["maps_url"],
                **({"idea_id": it["idea_id"]} if it.get("idea_id") else {})}

    @staticmethod
    def _plan_dates(trip: Trip, days: list[str] | None) -> list[date]:
        """The dates a draft covers. Required, so a request for one day doesn't turn into a plan for the whole trip."""
        if not days:
            raise ToolError('Pass days: the dates to plan, e.g. ["2027-03-15"]. If the group didn\'t say which days, '
                            "ask them first.")
        dates = sorted({parse_day(str(d), "days") for d in days})
        outside = [d.isoformat() for d in dates if not trip.start_date <= d <= trip.end_date]
        if outside:
            raise ToolError(f"{outside} are outside the trip ({iso(trip.start_date)} to {iso(trip.end_date)})")
        return dates

    def _check_place(self, trip: Trip, name: str, kind: str) -> tuple[dict, str]:
        """Look a stop up on the map. Returns the stop and "found", "not_found" or "unchecked" (the lookup failed,
        so verified is None rather than False)."""
        try:
            found = self.travel.find_place(name, trip.destination)
        except Exception as e:  # noqa: BLE001 - a map outage shouldn't stop planning
            log.warning("Place lookup failed for %r in %s: %s", name, trip.destination, e)
            found, status = None, "unchecked"
        else:
            status = "found" if found else "not_found"
        return {"name": name, "kind": kind,
                "location": osm.short_address(found) if found else trip.destination,
                "verified": None if status == "unchecked" else found is not None,
                "lat": found.lat if found else None, "lon": found.lon if found else None,
                "opening_hours": found.opening_hours if found else None,
                "maps_url": found.maps_url if found else osm.maps_url(name, trip.destination)}, status

    @staticmethod
    def _busy(trip: Trip, day: date, skip: Activity | None = None) -> list[dict]:
        """The slots plans already on the trip take on this day (agent/travel/planner.py `taken`), leaving out
        `skip` (the activity being moved)."""
        midnight = datetime.combine(day, time())
        out = []
        for a in trip.activities:
            if a.start is None or a is skip:
                continue
            if isinstance(a.start, datetime):
                if a.start.date() == day:
                    start = int((a.start - midnight).total_seconds() // 60)
                    end = int((as_datetime(a.end) - midnight).total_seconds() // 60) if a.end else start + 120
                    out += taken(start, end, a.lat, a.lon)
            elif a.start <= day <= _day(a.end or a.start):  # a plan with only dates covers those whole days
                out += taken(None, None, a.lat, a.lon)
        return out

    def _draft_from_places(self, trip: Trip, places: list[dict], dates: list[date],
                           ideas: list[dict]) -> tuple[list[dict], dict]:
        """The group's ideas first, then the agent's stops, each checked on the map, laid out into the free slots of
        those days (agent/travel/planner.py)."""
        for p in places:
            self._check_place_arg(p)
        # A place already on the trip isn't drafted again, and the same place twice (or an idea again) would be
        # looked up and scheduled twice.
        on_trip = {a.name.lower(): a.name for a in trip.activities}
        already = sorted({on_trip[i["name"].lower()] for i in ideas if i["name"].lower() in on_trip}
                         | {on_trip[p["name"].strip().lower()] for p in places if p["name"].strip().lower() in on_trip})
        idea_names = {i["name"].lower() for i in ideas}
        ideas = [i for i in ideas if i["name"].lower() not in on_trip]
        unique: dict[str, dict] = {}
        for p in places:
            key = p["name"].strip().lower()
            if key not in idea_names and key not in on_trip:
                unique.setdefault(key, p)
        places = list(unique.values())
        busy = {d: self._busy(trip, d) for d in dates}
        free = sum(len(planner.SLOTS) - len({b["slot"] for b in busy[d]}) for d in dates)
        if not free:
            raise ToolError("Those days are already full. Ask which plans to move, or pick other days.")
        cap = min(MAX_STOPS_PER_DAY * len(dates), MAX_STOPS, free)
        stops = [{**i, "hours": _hours(i)} for i in ideas[:cap]]  # ideas were checked on the map when saved
        room = cap - len(stops)
        not_found, unchecked = [], []
        for p in places[:room]:
            stop, status = self._check_place(trip, p["name"].strip(), p["kind"])
            if status == "not_found":
                not_found.append(stop["name"])
            elif status == "unchecked":
                unchecked.append(stop["name"])
            stops.append({**stop, "est_cost_cents": p.get("est_cost_cents"), "hours": _hours(stop)})
        plan = [{"date": day["date"].isoformat(), "items": [self._draft_item(it, day["date"]) for it in day["items"]]}
                for day in plan_days(stops, dates, busy)]
        extra = {"not_found": not_found, "map_check_failed": unchecked, "already_on_trip": already,
                 "ideas_used": [i["name"] for i in ideas[:cap]], "ideas_left": [i["name"] for i in ideas[cap:]],
                 "skipped": [p["name"] for p in places[room:]], "note": ESTIMATES_NOTE, "credit": osm.ATTRIBUTION}
        return plan, extra

    def _draft_from_provider(self, trip: Trip, dates: list[date], constraints: str | None) -> list[dict]:
        days = []
        ideas = self.travel.itinerary_items(trip.destination, 2 * len(dates), constraints)
        for i, day in enumerate(dates):
            d = day.isoformat()
            items = []
            for j, hour in enumerate((11, 19)):
                name, loc, cost = ideas[2 * i + j]
                items.append({"name": name, "location": loc,
                              "start": f"{d}T{hour}:00", "end": f"{d}T{hour + 2}:00",
                              "est_cost_cents": cost, "cost_is_per_person": True})
            days.append({"date": d, "items": items})
        return days

    def add_activity(self, trip_id: str, name: str | None = None, activity_id: str | None = None,
                     location: str | None = None, start: str | None = None, end: str | None = None,
                     est_cost_cents: int | None = None, cost_is_per_person: bool | None = None,
                     attendees: list[str] | None = None, important: bool | None = None,
                     booking_url: str | None = None, expense_id: str | None = None, day: str | None = None,
                     kind: str | None = None, idea_id: str | None = None) -> dict:
        trip = self._trip(trip_id)
        people = None if attendees is None else [trip.get_member(pid, active_only=True) for pid in attendees]
        fields = {"name": name, "location": location, "start": parse_day_or_time(start, "start"),
                  "end": parse_day_or_time(end, "end"), "est_cost_cents": est_cost_cents,
                  "cost_is_per_person": cost_is_per_person, "attendees": people, "important": important,
                  "booking_url": booking_url, "expense_id": expense_id}
        fields = {k: v for k, v in fields.items() if v is not None}
        if kind is not None and kind not in KINDS:
            raise ToolError("kind must be food, activity or night (leave it out for things like flights)")
        if activity_id:
            match = next((a for a in trip.activities if a.id == activity_id), None)
            if match is None:
                raise ToolError(f"No activity {activity_id!r}")
            if kind:
                fields["kind"] = kind
            if day and "start" not in fields:  # move it to a free slot of its kind on that day
                k = fields.get("kind") or match.kind
                if not k:
                    raise ToolError("It isn't a food, activity or night stop, so pass start with a time (or pass kind)")
                on = parse_day(day, "day")
                slot, _ = pick_slot(on, self._busy(trip, on, skip=match), {"kind": k, "hours": None},
                                    prefer=self._slot_of(match))
                if slot is None:  # nothing changed
                    return {"updated": False, "day_full": True, "day": on.isoformat(),
                            "plans_that_day": [a.name for a in trip.activities
                                               if a.start and _day(a.start) == on and a is not match],
                            "next_step": "Ask for a specific time or another day."}
                fields["start"], fields["end"] = _at(on, slot[2]), _at(on, slot[3])
            match.update(**fields)
            return {"activity_id": activity_id, "updated": True, "start": iso(match.start), "end": iso(match.end)}
        idea = None
        if idea_id:
            idea = next((i for i in trip.ideas if i["idea_id"] == idea_id), None)
            if idea is None:
                raise ToolError(f"No idea {idea_id!r}")
            fields.setdefault("name", idea["name"])
            kind = kind or idea["kind"]
            if idea.get("est_cost_cents") is not None:
                fields.setdefault("est_cost_cents", idea["est_cost_cents"])
        if not fields.get("name"):
            raise ToolError("name is required for a new activity")
        place, status = (idea, "found") if idea else (None, None)
        if kind and not idea:  # a place: check it on the map
            place, status = self._check_place(trip, fields["name"].strip(), kind)
        if place:
            fields.setdefault("location", place["location"])
            fields.update(lat=place["lat"], lon=place["lon"], verified=place["verified"])
        slot = None
        if day and "start" not in fields:
            if not place:
                raise ToolError("Pass kind (food, activity or night) with day so it gets the right slot, "
                                "or pass start with a time")
            on = parse_day(day, "day")
            slot, why = pick_slot(on, self._busy(trip, on), {**place, "hours": _hours(place)})
            if slot is None:  # nothing saved: the group picks a time, another day or the ideas list
                taken_by = [a.name for a in trip.activities if a.start and _day(a.start) == on]
                return {"created": False, "day_full": why == "full", "closed_then": why == "closed",
                        "day": on.isoformat(), "plans_that_day": taken_by,
                        "opening_hours": place.get("opening_hours"),
                        "next_step": "Ask for a specific time, another day, or the ideas list."}
            fields["start"], fields["end"] = _at(on, slot[2]), _at(on, slot[3])
        fields.setdefault("attendees", [p for p in trip.members if p.active])
        a = Activity(self._next_id("a", {a.id for a in trip.activities}), **fields, kind=kind, from_idea=bool(idea))
        trip.add_activity(a)
        if idea:
            trip.ideas.remove(idea)
        out = {"activity_id": a.id, "created": True, "start": iso(a.start), "end": iso(a.end),
               "outside_trip_dates": a.id in self._activities_outside(trip)}
        if place:
            out.update(slot=slot[0] if slot else None, location=a.location, verified=a.verified,
                       not_found=status == "not_found", map_check_failed=status == "unchecked",
                       maps_url=place["maps_url"], opening_hours=place.get("opening_hours"),
                       from_ideas=bool(idea), credit=osm.ATTRIBUTION)
        return out

    @staticmethod
    def _slot_of(a: Activity) -> str | None:
        """The slot of its kind a timed activity sits in, e.g. "dinner"."""
        if not isinstance(a.start, datetime) or not a.kind:
            return None
        start = a.start.hour * 60 + a.start.minute
        end = start + int((as_datetime(a.end) - a.start).total_seconds() // 60) if a.end else start + 120
        return next((b["slot"] for b in taken(start, end) if b["kind"] == a.kind), None)

    def remove_activity(self, trip_id: str, activity_id: str) -> dict:
        trip = self._trip(trip_id)
        a = trip.remove_activity(activity_id)
        back = (a.from_idea and bool(a.kind) and len(trip.ideas) < MAX_IDEAS
                and a.name.lower() not in {i["name"].lower() for i in trip.ideas})
        if back:  # it came off the ideas list, so it goes back on
            trip.ideas.append({"idea_id": self._next_id("i", {i["idea_id"] for i in trip.ideas}), "name": a.name,
                               "kind": a.kind, "location": a.location, "verified": a.verified, "lat": a.lat,
                               "lon": a.lon, "opening_hours": None, "maps_url": osm.maps_url(a.name, trip.destination),
                               "est_cost_cents": a.est_per_person_cents(), "suggested_by": None})
        return {"removed": True, "activity_id": a.id, "name": a.name, "back_on_ideas": back,
                "expense_still_logged": a.expense_id}

    def edit_draft(self, trip_id: str, draft_id: str, action: str, stop: str | None = None,
                   place: dict | None = None, day: str | None = None) -> dict:
        """One change to an unsaved draft: drop a stop, swap it for another place, move it to another day, or add
        a place to a day. The draft keeps its id. If the new spot has no free slot (or the place is closed then),
        nothing changes."""
        trip = self._trip(trip_id)
        if draft_id not in trip.itinerary_drafts:
            raise ToolError(f"No draft {draft_id!r}. Current: {sorted(trip.itinerary_drafts)}")
        if action not in ("drop", "swap", "move", "add"):
            raise ToolError("action must be drop, swap, move or add")
        draft = trip.itinerary_drafts[draft_id]
        old = old_day = None
        if action != "add":
            key = (stop or "").strip().lower()
            old_day, old = next(((d, it) for d in draft for it in d["items"] if it["name"].lower() == key),
                                (None, None))
            if old is None:
                raise ToolError(f"No stop {stop!r} in the draft. Stops: {[it['name'] for d in draft for it in d['items']]}")
        status = None
        if action == "drop":
            old_day["items"].remove(old)
        else:
            if action == "move":
                new, on, prefer = old, parse_day(day, "day"), old["slot"]
            else:  # swap or add: a new place, checked on the map
                self._check_place_arg(place)
                name = place["name"].strip()
                taken_names = {a.name.lower() for a in trip.activities} | {
                    it["name"].lower() for d in draft for it in d["items"] if it is not old}
                if name.lower() in taken_names:
                    raise ToolError(f"{name} is already on the trip or in this draft")
                checked, status = self._check_place(trip, name, place["kind"])
                new = {**checked, "est_cost_cents": place.get("est_cost_cents")}
                if action == "swap":
                    on, prefer = date.fromisoformat(old_day["date"]), old["slot"]
                else:
                    on, prefer = parse_day(day, "day"), None
            if on is None or not trip.start_date <= on <= trip.end_date:
                raise ToolError(f"day must be a date in the trip ({iso(trip.start_date)} to {iso(trip.end_date)})")
            target = next((d for d in draft if d["date"] == on.isoformat()), None)
            busy = self._busy(trip, on) + [{"slot": it["slot"], "kind": it["kind"], "lat": it["lat"], "lon": it["lon"]}
                                           for it in (target["items"] if target else []) if it is not old]
            slot, why = pick_slot(on, busy, {**new, "hours": _hours(new)}, prefer=prefer)
            if slot is None:
                return {"draft_id": draft_id, "changed": False, "day_full": why == "full",
                        "closed_then": why == "closed", "day": on.isoformat(),
                        "opening_hours": new.get("opening_hours"), "not_found": status == "not_found",
                        "next_step": "Nothing changed. Ask for another day or a different place."}
            if old is not None:
                old_day["items"].remove(old)
            if target is None:
                target = {"date": on.isoformat(), "items": []}
                draft.append(target)
                draft.sort(key=lambda d: d["date"])
            target["items"].append(self._draft_item(
                {**new, "slot": slot[0], "start_min": slot[2], "end_min": slot[3], "hours_conflict": False}, on))
            target["items"].sort(key=lambda it: it["start"])
        return {"draft_id": draft_id, "changed": True, "days": draft, "not_found": status == "not_found",
                "map_check_failed": status == "unchecked", "note": ESTIMATES_NOTE, "credit": osm.ATTRIBUTION}

    def find_nearby(self, trip_id: str, what: str, near: str | None = None, radius_m: int | None = None) -> dict:
        """The closest places of a kind ("pizza", "coffee", "pharmacy") to where the group is staying, or to `near`
        (a place someone names). Distances are worked out here, so the agent never does the math."""
        trip = self._trip(trip_id)
        radius = NEARBY_RADIUS_M if radius_m is None else radius_m
        if isinstance(radius, bool) or not isinstance(radius, int) or not 100 <= radius <= MAX_RADIUS_M:
            raise ToolError(f"radius_m must be 100 to {MAX_RADIUS_M} meters (about 3 miles)")
        if nearby.normalize(what) is None:
            raise ToolError("what must be a short word or two, like pizza, coffee, bar or pharmacy")
        if near and str(near).strip():
            if not trip.destination:
                raise ToolError("Set the destination first, so the place can be found on the map")
            try:
                found = self.travel.find_place(str(near).strip(), trip.destination)
            except Exception as e:  # noqa: BLE001
                log.warning("Lookup failed for %r in %s: %s", near, trip.destination, e)
                raise ToolError("The map lookup failed. Say so and suggest trying again in a minute.") from e
            if found is None:
                raise ToolError(f"Couldn't find {near!r} on the map near {trip.destination}. "
                                "Ask for an address or a well-known landmark.")
            origin = {"name": str(near).strip(), "address": osm.short_address(found), "lat": found.lat,
                      "lon": found.lon}
        elif trip.lodging:
            origin = trip.lodging
        else:
            raise ToolError("No lodging saved, so there's no starting point. Ask where the group is staying (and "
                            "offer to save it with update_trip lodging), or pass near.")
        try:
            places = self.travel.find_nearby(what, origin["lat"], origin["lon"], radius)
        except Exception as e:  # noqa: BLE001 - a busy map server gets a friendly reply, not a crash
            log.warning("Nearby search for %r failed: %s", what, e)
            raise ToolError("The map search is busy right now. Say so and suggest trying again in a minute.") from e
        ranked = sorted(((nearby.distance_m(origin["lat"], origin["lon"], p["lat"], p["lon"]), p) for p in places),
                        key=lambda mp: mp[0])
        ranked = [(m, p) for m, p in ranked if m <= radius]
        results = []
        for m, p in ranked[:MAX_NEARBY]:
            distance, walk = nearby.describe_distance(m)
            where = f"{p['street']}, {trip.destination}" if p.get("street") else trip.destination or ""
            results.append({"name": p["name"], "distance": distance, "walk": walk, "address": p.get("street"),
                            "opening_hours": p.get("opening_hours"), "cuisine": p.get("cuisine"),
                            "maps_url": osm.maps_url(p["name"], where)})
        within = f"{radius / 1609.344:.1f}".rstrip("0").rstrip(".") + " mi"  # 1600 m -> "1 mi", 400 m -> "0.2 mi"
        out = {"what": what, "near": origin["name"], "near_address": origin.get("address"), "within": within,
               "results": results, "more_found": max(0, len(ranked) - MAX_NEARBY), "note": NEARBY_NOTE,
               "credit": osm.ATTRIBUTION}
        if not results:
            out["next_step"] = (f"Nothing found within {within}. Say so and offer to look farther "
                                f"(radius_m up to {MAX_RADIUS_M}).")
        return out

    def save_idea(self, trip_id: str, name: str | None = None, kind: str | None = None,
                  est_cost_cents: int | None = None, idea_id: str | None = None, remove: bool = False,
                  suggested_by: str | None = None) -> dict:
        trip = self._trip(trip_id)
        if remove:  # anyone on the trip can drop an idea
            key = (name or "").strip().lower()
            match = next((i for i in trip.ideas if i["idea_id"] == idea_id or (key and i["name"].lower() == key)),
                         None)
            if match is None:
                raise ToolError(f"No idea {idea_id or name!r}. Ideas: {[i['name'] for i in trip.ideas]}")
            trip.ideas.remove(match)
            return {"removed": True, "name": match["name"], "ideas_left": len(trip.ideas)}
        if not (name or "").strip() or kind not in KINDS:
            raise ToolError("An idea needs a name and a kind: food, activity or night")
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
        if not trip.destination:
            raise ToolError("Set the destination before saving ideas, so they can be checked on the map")
        place, status = self._check_place(trip, name.strip(), kind)
        idea = {"idea_id": self._next_id("i", {i["idea_id"] for i in trip.ideas}), **place,
                "est_cost_cents": est_cost_cents, "suggested_by": suggested_by}
        trip.ideas.append(idea)
        return {"saved": True, "idea": idea, "not_found": status == "not_found",
                "map_check_failed": status == "unchecked", "ideas_count": len(trip.ideas), "credit": osm.ATTRIBUTION}

    def get_travel_tips(self, trip_id: str, destination: str, multipliers: list[float],
                        prices_only: bool = False, interests: list[str] | None = None) -> dict:
        trip = self._trip(trip_id)
        if not multipliers or any(m <= 0 for m in multipliers):
            raise ToolError("multipliers must be positive numbers, e.g. [0.5, 0.75, 1, 1.25, 1.5, 2]")
        active = [p for p in trip.members if p.active]
        totals = [p.budget.total_cents for p in active if p.budget]
        missing = [p.id for p in active if p.budget is None]
        if not totals:
            return {"average_cents": None, "missing_budgets": missing, "tiers": [],
                    "note": "Nobody has set a budget yet; ask members in the group for theirs."}
        avg = round(sum(totals) / len(totals))
        tiers = []
        for m in multipliers:
            tier = {"multiplier": m, "budget_cents": rules.tier_price(avg, m)}
            if not prices_only:
                tier.update(self.travel.tips(destination, tier, iso(trip.start_date), iso(trip.end_date)))
            tiers.append(tier)
        return {"destination": destination, "average_cents": avg, "budgets_counted": len(totals),
                "budgets": {p.id: p.budget.total_cents for p in active if p.budget},
                "missing_budgets": missing, "tiers": tiers, "interests": interests or []}

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
        s["itinerary_drafts"] = sorted(trip.itinerary_drafts)
        s["ideas"] = trip.ideas
        for view, a in zip(s["activities"], trip.activities):
            if a.verified is not None:  # came from an itinerary draft: rebuild its Maps link
                view["maps_url"] = osm.maps_url(a.name, a.location or trip.destination)
        # Budgets are shared with everyone on the trip (decided Oct 28, 2026).
        s["budgets"] = {p.id: {"total_cents": p.budget.total_cents,
                               "limits": {c.name: v for c, v in p.budget.limits.items()}}
                        for p in trip.members if p.budget}
        return s

    # ------------------------------------------------------------- not a tool
    def summary(self, trip_id: str) -> dict:
        trip = self._trip(trip_id)
        now = self._now()
        return {
            "trip": {"id": trip.id, "name": trip.name, "status": trip.status.name,
                     "destination": trip.destination, "start_date": iso(trip.start_date),
                     "end_date": iso(trip.end_date), "target_break": trip.target_break,
                     "base_currency": trip.base_currency, "group_budget_cents": trip.group_budget,
                     "leader_id": trip.leader_id, "leader_approval": sorted(trip.leader_approval),
                     "auto_log_mode": trip.auto_log_mode, "planning_notes": trip.planning_notes,
                     "lodging": trip.lodging},
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
            "ideas": [{"idea_id": i["idea_id"], "name": i["name"], "kind": i["kind"]} for i in trip.ideas],
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
