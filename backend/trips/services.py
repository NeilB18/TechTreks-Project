"""DjangoBackend: the Backend protocol (agent/backend/protocol.py) over the database.

Each tool call loads the whole trip into the same dataclasses the fake backend
uses, runs FakeBackend's logic on it, and writes the trip back in one
transaction. The rules (splits, opt-outs, refunds, balances, warnings) live in
one place (the fake backend, which takes the money rules from classes/), so the
database backend can't drift from the tested fake. Trips are small (a dozen
people, a few hundred rows), so whole-trip load/save is cheap.
"""

import functools
import inspect

from django.db import transaction
from django.utils import timezone

from agent.backend.fake import models as dc
from agent.backend.fake.store import FakeBackend
from agent.backend.protocol import BACKEND_TOOLS, ToolError
from trips import models as m

READ_ONLY = {"get_balances", "get_budget_status", "convert_currency", "get_trip", "get_travel_tips"}


# ------------------------------------------------------------------- load
def load_trip(trip_id: str, lock: bool = False) -> dc.Trip:
    qs = m.Trip.objects.select_for_update() if lock else m.Trip.objects
    try:
        row = qs.get(id=trip_id)
    except m.Trip.DoesNotExist:
        raise ToolError(f"No trip with id {trip_id!r}") from None
    trip = dc.Trip(id=row.id, name=row.name, status=row.status, destination=row.destination,
                   start_date=row.start_date, end_date=row.end_date, target_break=row.target_break,
                   base_currency=row.base_currency, group_budget=row.group_budget,
                   leader_id=row.leader_id, leader_approval=list(row.leader_approval),
                   auto_log_mode=row.auto_log_mode)
    for p in row.people.all():
        trip.members[p.person_id] = dc.Person(id=p.person_id, name=p.name, chat_user_id=p.chat_user_id,
                                              payment_handle=p.payment_handle, active=p.active)
    for b in m.Budget.objects.filter(person__trip=row).select_related("person"):
        trip.budgets[b.person.person_id] = dc.Budget(owner_id=b.person.person_id,
                                                     total_cents=b.total_cents, limits=dict(b.limits))
    trip.exclusions = {(x.person_id, x.category) for x in row.exclusions.all()}
    for e in row.expenses.prefetch_related("splits"):
        trip.expenses.append(dc.Expense(
            id=e.id, paid_by=e.paid_by, amount_cents=e.amount_cents, original_amount=e.original_amount,
            original_currency=e.original_currency, fx_rate=e.fx_rate, description=e.description,
            category=e.category, splits={s.person_id: s.cents for s in e.splits.all()},
            created_at=e.created_at, source_message=e.source_message))
    for r in row.refunds.prefetch_related("shares"):
        trip.refunds.append(dc.Refund(
            id=r.refund_id, expense_id=r.expense_id, amount_cents=r.amount_cents,
            original_amount=r.original_amount, currency=r.currency, note=r.note,
            per_person={s.person_id: s.cents for s in r.shares.all()}, created_at=r.created_at))
    for a in row.activities.all():
        trip.activities.append(dc.Activity(
            id=a.activity_id, name=a.name, location=a.location, start=a.start, end=a.end,
            est_cost_cents=a.est_cost_cents, cost_is_per_person=a.cost_is_per_person,
            attendees=list(a.attendees), important=a.important, booking_url=a.booking_url,
            expense_id=a.expense_id))
    for p in row.polls.prefetch_related("votes"):
        trip.polls.append(dc.Poll(id=p.id, question=p.question, options=list(p.options),
                                  votes={v.person_id: v.option for v in p.votes.all()},
                                  closes_at=p.closes_at, is_open=p.is_open))
    for r in row.reminders.all():
        trip.reminders.append(dc.Reminder(id=r.reminder_id, message=r.message, due_at=r.due_at,
                                          audience=r.audience, sent=r.sent, created_by=r.created_by))
    trip.itinerary_drafts = {d.draft_id: d.days for d in row.itinerary_drafts.all()}
    return trip


# ------------------------------------------------------------------- save
def save_trip(trip: dc.Trip) -> None:
    """Write a trip back. People and budgets are updated in place (other tables may point at
    Person rows); everything else is replaced, in list order."""
    row, _ = m.Trip.objects.update_or_create(id=trip.id, defaults=dict(
        name=trip.name, status=trip.status, destination=trip.destination, start_date=trip.start_date,
        end_date=trip.end_date, target_break=trip.target_break, base_currency=trip.base_currency,
        group_budget=trip.group_budget, leader_id=trip.leader_id,
        leader_approval=list(trip.leader_approval), auto_log_mode=trip.auto_log_mode))

    people = {}
    for i, p in enumerate(trip.members.values()):
        people[p.id], _ = m.Person.objects.update_or_create(trip=row, person_id=p.id, defaults=dict(
            name=p.name, chat_user_id=p.chat_user_id, payment_handle=p.payment_handle,
            active=p.active, position=i))
    for pid, b in trip.budgets.items():
        m.Budget.objects.update_or_create(person=people[pid], defaults=dict(
            total_cents=b.total_cents, limits=dict(b.limits)))
    m.Budget.objects.filter(person__trip=row).exclude(person__person_id__in=trip.budgets).delete()

    row.exclusions.all().delete()
    m.Exclusion.objects.bulk_create(m.Exclusion(trip=row, person_id=pid, category=cat)
                                    for pid, cat in sorted(trip.exclusions))
    row.expenses.all().delete()
    for i, e in enumerate(trip.expenses):
        er = m.Expense.objects.create(
            id=e.id, trip=row, paid_by=e.paid_by, amount_cents=e.amount_cents,
            original_amount=e.original_amount, original_currency=e.original_currency, fx_rate=e.fx_rate,
            description=e.description, category=e.category, created_at=e.created_at,
            source_message=e.source_message, position=i)
        m.ExpenseSplit.objects.bulk_create(m.ExpenseSplit(expense=er, person_id=pid, cents=c, position=j)
                                           for j, (pid, c) in enumerate(e.splits.items()))
    row.refunds.all().delete()
    for i, r in enumerate(trip.refunds):
        rr = m.Refund.objects.create(
            trip=row, refund_id=r.id, expense_id=r.expense_id, amount_cents=r.amount_cents,
            original_amount=r.original_amount, currency=r.currency, note=r.note,
            created_at=r.created_at, position=i)
        m.RefundShare.objects.bulk_create(m.RefundShare(refund=rr, person_id=pid, cents=c, position=j)
                                          for j, (pid, c) in enumerate(r.per_person.items()))
    row.activities.all().delete()
    m.Activity.objects.bulk_create(m.Activity(
        trip=row, activity_id=a.id, name=a.name, location=a.location, start=a.start, end=a.end,
        est_cost_cents=a.est_cost_cents, cost_is_per_person=a.cost_is_per_person,
        attendees=list(a.attendees), important=a.important, booking_url=a.booking_url,
        expense_id=a.expense_id, position=i) for i, a in enumerate(trip.activities))
    row.polls.all().delete()
    for i, p in enumerate(trip.polls):
        pr = m.Poll.objects.create(id=p.id, trip=row, question=p.question, options=list(p.options),
                                   closes_at=p.closes_at, is_open=p.is_open, position=i)
        m.PollVote.objects.bulk_create(m.PollVote(poll=pr, person_id=pid, option=o)
                                       for pid, o in p.votes.items())
    row.reminders.all().delete()
    m.Reminder.objects.bulk_create(m.Reminder(
        trip=row, reminder_id=r.id, message=r.message, due_at=r.due_at, audience=r.audience,
        sent=r.sent, created_by=r.created_by, position=i) for i, r in enumerate(trip.reminders))
    row.itinerary_drafts.all().delete()
    m.ItineraryDraft.objects.bulk_create(m.ItineraryDraft(trip=row, draft_id=k, days=v)
                                         for k, v in trip.itinerary_drafts.items())


# ---------------------------------------------------------------- backend
class _DbScopedFake(FakeBackend):
    """FakeBackend whose global id checks look at the whole database, not just the loaded trip."""

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
    fake_method = getattr(FakeBackend, name)
    sig = inspect.signature(fake_method)

    @functools.wraps(fake_method)
    def method(self, *args, **kwargs):
        bound = sig.bind(None, *args, **kwargs)
        call = dict(bound.arguments)
        call.pop("self")
        call.update(call.pop("kw", {}))  # convert_currency's **kw ("from"/"to")
        return self._run(name, call)

    return method


class DjangoBackend:
    """Implements every tool in BACKEND_TOOLS with FakeBackend's signatures and results."""

    def __init__(self, now: str | None = None):
        self.now = now

    def _fake(self) -> FakeBackend:
        return _DbScopedFake(now=self.now or timezone.now().isoformat(timespec="seconds"))

    def _run(self, name: str, args: dict) -> dict:
        fb = self._fake()
        with transaction.atomic():
            trip_id = _trip_id_for(args)
            if trip_id is not None:
                trip = load_trip(trip_id, lock=name not in READ_ONLY)
                fb.trips[trip.id] = trip
            result = getattr(fb, name)(**args)
            if trip_id is not None and name not in READ_ONLY:
                save_trip(fb.trips[trip_id])
        return result

    # Not tools ------------------------------------------------------------
    def summary(self, trip_id: str) -> dict:
        fb = self._fake()
        fb.trips[trip_id] = load_trip(trip_id)
        return fb.summary(trip_id)

    def load_seed(self, seed: dict) -> None:
        """Create a trip from a scenario seed (tests and demos)."""
        fb = self._fake()
        if "now" in seed:
            self.now = str(seed["now"])
        with transaction.atomic():
            fb.load_seed(seed)
            for trip in fb.trips.values():
                save_trip(trip)

    @property
    def trips(self) -> "_TripsView":
        """Read access shaped like FakeBackend.trips, for the scenario checker."""
        return _TripsView()

    def settle_up(self, trip: dc.Trip) -> dict:
        return FakeBackend().settle_up(trip)


class _TripsView:
    def __getitem__(self, trip_id: str) -> dc.Trip:
        return load_trip(trip_id)


for _name in BACKEND_TOOLS:
    setattr(DjangoBackend, _name, _tool(_name))
