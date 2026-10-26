"""DjangoBackend: the Backend protocol (agent/backend/protocol.py) over the database.

Each tool call loads the whole trip into trip_model objects, runs TripEngine on
it, and writes the trip back in one transaction. The rules live in one place
(trip_model/, used through the engine), so the database backend can't drift from
the in-memory one the tests use. Trips are small (a dozen people, a few hundred
rows), so whole-trip load/save is cheap.
"""

import functools
import inspect

from django.db import transaction
from django.utils import timezone

from agent.backend.core.engine import TripEngine, iso, parse_day, parse_day_or_time, parse_time
from agent.backend.protocol import BACKEND_TOOLS, ToolError
from trip_model.activity import Activity
from trip_model.budget import Budget
from trip_model.category import Category
from trip_model.expense import Expense
from trip_model.person import Person
from trip_model.poll import Poll
from trip_model.refund import Refund
from trip_model.reminder import Reminder
from trip_model.trip import Trip
from trip_model.trip_status import TripStatus
from trips import models as m

READ_ONLY = {"get_balances", "get_budget_status", "convert_currency", "get_trip", "get_travel_tips"}


# ------------------------------------------------------------------- load
def load_trip(trip_id: str, lock: bool = False) -> Trip:
    qs = m.Trip.objects.select_for_update() if lock else m.Trip.objects
    try:
        row = qs.get(id=trip_id)
    except m.Trip.DoesNotExist:
        raise ToolError(f"No trip with id {trip_id!r}") from None
    trip = Trip(row.id, row.name, status=TripStatus[row.status], destination=row.destination,
                start_date=parse_day(row.start_date, "start_date"), end_date=parse_day(row.end_date, "end_date"),
                target_break=row.target_break, base_currency=row.base_currency, group_budget=row.group_budget,
                leader_id=row.leader_id, leader_approval=list(row.leader_approval),
                auto_log_mode=row.auto_log_mode)
    for p in row.people.all():
        trip.add_member(Person(p.person_id, p.name, p.chat_user_id, p.payment_handle, active=p.active))
    for b in m.Budget.objects.filter(person__trip=row).select_related("person"):
        pid = b.person.person_id
        trip.get_member(pid).budget = Budget(pid, b.total_cents, {Category[c]: v for c, v in b.limits.items()})
    trip.opt_outs = {(x.person_id, Category[x.category]) for x in row.exclusions.all()}
    for e in row.expenses.prefetch_related("splits"):
        trip.add_expense(Expense(
            e.id, trip.get_member(e.paid_by), e.amount_cents, e.description, Category[e.category],
            splits={s.person_id: s.cents for s in e.splits.all()},
            created_at=parse_time(e.created_at, "created_at"), source_message=e.source_message,
            original_amount=e.original_amount, original_currency=e.original_currency, fx_rate=e.fx_rate))
    for r in row.refunds.prefetch_related("shares"):
        trip.get_expense(r.expense_id).refunds.append(Refund(
            r.refund_id, r.expense_id, r.amount_cents, {s.person_id: s.cents for s in r.shares.all()},
            note=r.note, created_at=parse_time(r.created_at, "created_at"),
            original_amount=r.original_amount, currency=r.currency))
    for a in row.activities.all():
        trip.add_activity(Activity(
            a.activity_id, a.name, location=a.location, start=parse_day_or_time(a.start, "start"),
            end=parse_day_or_time(a.end, "end"), est_cost_cents=a.est_cost_cents,
            cost_is_per_person=a.cost_is_per_person, attendees=[trip.get_member(pid) for pid in a.attendees],
            important=a.important, booking_url=a.booking_url, expense_id=a.expense_id))
    for p in row.polls.prefetch_related("votes"):
        trip.add_poll(Poll(p.id, p.question, list(p.options),
                           closes_at=parse_time(p.closes_at, "closes_at") if p.closes_at else None,
                           is_open=p.is_open, votes={v.person_id: v.option for v in p.votes.all()}))
    for r in row.reminders.all():
        trip.add_reminder(reminder_from_row(trip, r))
    trip.itinerary_drafts = {d.draft_id: d.days for d in row.itinerary_drafts.all()}
    return trip


def reminder_from_row(trip: Trip, r: m.Reminder) -> Reminder:
    audience = "all" if r.audience == "all" else [trip.get_member(pid) for pid in r.audience]
    return Reminder(r.message, parse_time(r.due_at, "due_at"), audience, sent=r.sent,
                    created_by=r.created_by, id=r.reminder_id)


# ------------------------------------------------------------------- save
def save_trip(trip: Trip) -> None:
    """Write a trip back. People and budgets are updated in place (other tables may point at
    Person rows); everything else is replaced, in list order."""
    row, _ = m.Trip.objects.update_or_create(id=trip.id, defaults=dict(
        name=trip.name, status=trip.status.name, destination=trip.destination,
        start_date=iso(trip.start_date), end_date=iso(trip.end_date), target_break=trip.target_break,
        base_currency=trip.base_currency, group_budget=trip.group_budget, leader_id=trip.leader_id,
        leader_approval=list(trip.leader_approval), auto_log_mode=trip.auto_log_mode))

    people = {}
    for i, p in enumerate(trip.members):
        people[p.id], _ = m.Person.objects.update_or_create(trip=row, person_id=p.id, defaults=dict(
            name=p.name, chat_user_id=p.chat_user_id, payment_handle=p.payment_handle,
            active=p.active, position=i))
    with_budget = [p for p in trip.members if p.budget is not None]
    for p in with_budget:
        m.Budget.objects.update_or_create(person=people[p.id], defaults=dict(
            total_cents=p.budget.total_cents, limits={c.name: v for c, v in p.budget.limits.items()}))
    m.Budget.objects.filter(person__trip=row).exclude(
        person__person_id__in=[p.id for p in with_budget]).delete()

    row.exclusions.all().delete()
    m.Exclusion.objects.bulk_create(m.Exclusion(trip=row, person_id=pid, category=cat)
                                    for pid, cat in sorted((pid, c.name) for pid, c in trip.opt_outs))
    row.expenses.all().delete()
    for i, e in enumerate(trip.expenses):
        er = m.Expense.objects.create(
            id=e.id, trip=row, paid_by=e.paid_by.id, amount_cents=e.amount_cents,
            original_amount=e.original_amount, original_currency=e.original_currency, fx_rate=e.fx_rate,
            description=e.description, category=e.category.name, created_at=iso(e.created_at),
            source_message=e.source_message or "", position=i)
        m.ExpenseSplit.objects.bulk_create(m.ExpenseSplit(expense=er, person_id=pid, cents=c, position=j)
                                           for j, (pid, c) in enumerate(e.splits.items()))
    row.refunds.all().delete()
    for i, r in enumerate(trip.refunds):
        rr = m.Refund.objects.create(
            trip=row, refund_id=r.id, expense_id=r.expense_id, amount_cents=r.amount_cents,
            original_amount=r.original_amount, currency=r.currency, note=r.note,
            created_at=iso(r.created_at), position=i)
        m.RefundShare.objects.bulk_create(m.RefundShare(refund=rr, person_id=pid, cents=c, position=j)
                                          for j, (pid, c) in enumerate(r.per_person.items()))
    row.activities.all().delete()
    m.Activity.objects.bulk_create(m.Activity(
        trip=row, activity_id=a.id, name=a.name, location=a.location, start=iso(a.start), end=iso(a.end),
        est_cost_cents=a.est_cost_cents, cost_is_per_person=a.cost_is_per_person,
        attendees=[p.id for p in a.attendees], important=a.important, booking_url=a.booking_url,
        expense_id=a.expense_id, position=i) for i, a in enumerate(trip.activities))
    row.polls.all().delete()
    for i, p in enumerate(trip.polls):
        pr = m.Poll.objects.create(id=p.id, trip=row, question=p.question, options=list(p.options),
                                   closes_at=iso(p.closes_at), is_open=p.is_open, position=i)
        m.PollVote.objects.bulk_create(m.PollVote(poll=pr, person_id=pid, option=o)
                                       for pid, o in p.votes.items())
    row.reminders.all().delete()
    m.Reminder.objects.bulk_create(m.Reminder(
        trip=row, reminder_id=r.id, message=r.message, due_at=iso(r.due_at),
        audience=r.audience if r.audience == "all" else [p.id for p in r.audience],
        sent=r.sent, created_by=r.created_by, position=i) for i, r in enumerate(trip.reminders))
    row.itinerary_drafts.all().delete()
    m.ItineraryDraft.objects.bulk_create(m.ItineraryDraft(trip=row, draft_id=k, days=v)
                                         for k, v in trip.itinerary_drafts.items())


# ---------------------------------------------------------------- backend
class _DbScopedEngine(TripEngine):
    """TripEngine whose global id checks look at the whole database, not just the loaded trip."""

    def _all_expense_ids(self) -> set[str]:
        return set(m.Expense.objects.values_list("id", flat=True))

    def _all_poll_ids(self) -> set[str]:
        return set(m.Poll.objects.values_list("id", flat=True))


def _trip_id_for(args: dict) -> str | None:
    if "trip_id" in args:
        return args["trip_id"]
    if "expense_id" in args:
        row = m.Expense.objects.filter(id=args["expense_id"]).values("trip_id").first()
        if not row:
            raise ToolError(f"No expense with id {args['expense_id']!r}")
        return row["trip_id"]
    if "poll_id" in args:
        row = m.Poll.objects.filter(id=args["poll_id"]).values("trip_id").first()
        if not row:
            raise ToolError(f"No poll with id {args['poll_id']!r}")
        return row["trip_id"]
    return None  # convert_currency


def _tool(name: str):
    engine_method = getattr(TripEngine, name)
    sig = inspect.signature(engine_method)

    @functools.wraps(engine_method)
    def method(self, *args, **kwargs):
        bound = sig.bind(None, *args, **kwargs)
        call = dict(bound.arguments)
        call.pop("self")
        call.update(call.pop("kw", {}))  # convert_currency's **kw ("from"/"to")
        return self._run(name, call)

    return method


class DjangoBackend:
    """Implements every tool in BACKEND_TOOLS with TripEngine's signatures and results."""

    def __init__(self, now: str | None = None):
        self.now = now

    def _engine(self) -> TripEngine:
        return _DbScopedEngine(now=self.now or timezone.now().isoformat(timespec="seconds"))

    def _run(self, name: str, args: dict) -> dict:
        engine = self._engine()
        with transaction.atomic():
            trip_id = _trip_id_for(args)
            if trip_id is not None:
                trip = load_trip(trip_id, lock=name not in READ_ONLY)
                engine.trips[trip.id] = trip
            result = getattr(engine, name)(**args)
            if trip_id is not None and name not in READ_ONLY:
                save_trip(engine.trips[trip_id])
        return result

    # Not tools ------------------------------------------------------------
    def summary(self, trip_id: str) -> dict:
        engine = self._engine()
        engine.trips[trip_id] = load_trip(trip_id)
        return engine.summary(trip_id)

    def load_seed(self, seed: dict) -> None:
        """Create a trip from a scenario seed (tests and demos)."""
        engine = self._engine()
        if "now" in seed:
            self.now = str(seed["now"])
        with transaction.atomic():
            engine.load_seed(seed)
            for trip in engine.trips.values():
                save_trip(trip)

    @property
    def trips(self) -> "_TripsView":
        """Read access shaped like TripEngine.trips, for the scenario checker."""
        return _TripsView()

    def settle_up(self, trip: Trip) -> dict:
        return TripEngine().settle_up(trip)


class _TripsView:
    def __getitem__(self, trip_id: str) -> Trip:
        return load_trip(trip_id)


for _name in BACKEND_TOOLS:
    setattr(DjangoBackend, _name, _tool(_name))
