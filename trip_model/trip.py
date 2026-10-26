# class Trip:
#     id; name; status (PLANNING / BOOKED / ACTIVE / DONE)
#     destination | None; start_date | None; end_date | None   # empty until a poll decides them
#     target_break | None            # "spring break", "fall break", etc.
#     base_currency                  # "USD"; the MVP is USD-only
#     group_budget | None            # per-person cents of the tier the leader locked in
#     leader_id | None; leader_approval: list[str]; auto_log_mode | None
#         # stored only; whether the leader feature stays is still being decided
#     members: list[Person]; activities; expenses; polls; reminders
#     opt_outs: set[(person_id, Category)]   # e.g. ("jake", DRINKS)
#     itinerary_drafts: dict[draft_id, list[day]]
#
#     get_member(person_id, active_only=False); active_member_ids()
#     add_member(); remove_member(person_id) -> ids of activities they left
#     set_opt_out(); remove_opt_out()
#     split_people(person_ids, category, exclude, overrides) -> (people, opted_out)
#     add_expense(); get_expense(); delete_expense(); refunds; add_refund()
#     add_activity(); add_poll(); add_reminder()
#     itinerary_by_day() -> dict[date, list[Activity]]
#     spent_by_category(person=None) -> dict[Category, int]
#     balances() -> dict[person_id, int]
#     settlement_plan() -> list[(from_person_id, to_person_id, amount_cents)]   # suggestion only
#     record_settlement(from_person_id, to_person_id, amount_cents, payment_id)

import heapq
from datetime import date, datetime

from .activity import Activity, as_datetime
from .budget import spent
from .category import Category
from .expense import Expense
from .person import Person
from .poll import Poll
from .refund import Refund
from .reminder import Reminder
from .trip_status import TripStatus

class Trip:
    def __init__(self, id, name, status: TripStatus = TripStatus.PLANNING,
                 destination=None, start_date: date | None = None,
                 end_date: date | None = None, target_break=None, base_currency="USD",
                 group_budget=None, leader_id=None, leader_approval: list[str] | None = None,
                 auto_log_mode=None):
        self.id = id
        self.name = name
        self.status = status
        self.destination = destination
        self.start_date = start_date
        self.end_date = end_date
        self.target_break = target_break
        self.base_currency = base_currency
        self.group_budget = group_budget
        self.leader_id = leader_id
        self.leader_approval = leader_approval if leader_approval is not None else []
        self.auto_log_mode = auto_log_mode
        self.members: list[Person] = []
        self.activities: list[Activity] = []
        self.expenses: list[Expense] = []
        self.polls: list[Poll] = []
        self.reminders: list[Reminder] = []
        self.opt_outs: set[tuple] = set()
        self.itinerary_drafts: dict[str, list[dict]] = {}

    def member_ids(self):
        return {member.id for member in self.members}

    def active_member_ids(self):
        return [member.id for member in self.members if member.active]

    def get_member(self, person_id, active_only=False):
        for member in self.members:
            if member.id == person_id:
                if active_only and not member.active:
                    raise ValueError(f"{person_id!r} has been removed from the trip and can't be in "
                                     "new splits or activities")
                return member
        raise ValueError(f"{person_id!r} is not a member of trip {self.id!r}. Members: {sorted(self.member_ids())}")

    def add_member(self, person: Person):
        if person.id in self.member_ids():
            return
        self.members.append(person)
        if self not in person.trips:
            person.trips.append(self)

    def remove_member(self, person_id):
        # Dropouts keep their past splits (they still owe); they leave future splits and activities.
        person = self.get_member(person_id)
        if not person.active:
            raise ValueError(f"{person_id!r} was already removed")
        person.active = False
        left = []
        for activity in self.activities:
            if person in activity.attendees:
                activity.attendees.remove(person)
                left.append(activity.id)
        return left

    def set_opt_out(self, person_id, category: Category):
        self.get_member(person_id)
        self.opt_outs.add((person_id, category))

    def remove_opt_out(self, person_id, category: Category):
        self.get_member(person_id)
        self.opt_outs.discard((person_id, category))

    def split_people(self, person_ids: list, category: Category, exclude=(), overrides=()):
        # Who an equal split is between: no dropouts, no one excluded for this expense, and no one
        # who opted out of the category unless they agreed to be included (overrides).
        people, opted_out = [], []
        for person_id in dict.fromkeys(person_ids):  # dedupe, keep order
            self.get_member(person_id, active_only=True)
            if person_id in exclude:
                continue
            if (person_id, category) in self.opt_outs and person_id not in overrides:
                opted_out.append(person_id)
                continue
            people.append(person_id)
        if not people:
            raise ValueError("Nobody left in the split after exclusions")
        return people, opted_out

    def add_expense(self, expense: Expense):
        member_ids = self.member_ids()
        if any(existing.id == expense.id for existing in self.expenses):
            raise ValueError(f"Expense {expense.id} has already been recorded.")
        if expense.paid_by.id not in member_ids:
            raise ValueError("Payer is not on this trip.")
        if any(person_id not in member_ids for person_id in expense.splits):
            raise ValueError("Every person in the split must be on this trip.")
        if sum(expense.splits.values()) != 0:
            raise ValueError("Splits must sum to zero.")
        self.expenses.append(expense)

    def get_expense(self, expense_id):
        for expense in self.expenses:
            if expense.id == expense_id:
                return expense
        raise ValueError(f"No expense with id {expense_id!r}")

    def delete_expense(self, expense_id):
        # Its refunds go with it, and any activity paid by it is unlinked.
        expense = self.get_expense(expense_id)
        self.expenses.remove(expense)
        for activity in self.activities:
            if activity.expense_id == expense_id:
                activity.expense_id = None
        return expense

    @property
    def refunds(self) -> list[Refund]:
        return [refund for expense in self.expenses for refund in expense.refunds]

    def add_refund(self, expense_id, refund_id, amount_cents, **details):
        if any(refund.id == refund_id for refund in self.refunds):
            raise ValueError(f"Refund {refund_id} has already been recorded.")
        return self.get_expense(expense_id).add_refund(refund_id, amount_cents, **details)

    def add_activity(self, activity: Activity):
        member_ids = self.member_ids()
        if any(person.id not in member_ids for person in activity.attendees):
            raise ValueError("Every attendee must be on this trip.")
        self.activities.append(activity)

    def add_poll(self, poll: Poll):
        self.polls.append(poll)

    def add_reminder(self, reminder: Reminder):
        self.reminders.append(reminder)

    def itinerary_by_day(self):
        # Activities without a start time aren't on a day yet.
        itinerary = {}
        for activity in sorted((a for a in self.activities if a.start is not None),
                               key=lambda a: as_datetime(a.start)):
            itinerary.setdefault(as_datetime(activity.start).date(), []).append(activity)
        return itinerary

    def spent_by_category(self, person: Person | None = None):
        # Whole-group spending, or just this person's shares. Refunds come off; settlements are not spending.
        categories = [category for category in Category if category != Category.SETTLEMENT]
        if person is not None:
            return {category: spent(person.id, category, self.expenses) for category in categories}
        totals = {category: 0 for category in categories}
        for expense in self.expenses:
            if expense.category != Category.SETTLEMENT:
                totals[expense.category] += expense.amount_cents - expense.refunded_cents()
        return totals

    def balances(self):
        balance = {member.id: 0 for member in self.members}
        for expense in self.expenses:
            for person_id, delta in expense.net_changes().items():
                balance[person_id] += delta
        if sum(balance.values()) != 0:
            raise RuntimeError("Balances do not sum to zero.")
        return balance

    def settlement_plan(self):
        b = {person_id: amount for person_id, amount in self.balances().items() if amount != 0}
        if not b:
            return []
        return self._greedy_settlements(b)

    def _greedy_settlements(self, b: dict):
        # Exact opposites pay each other first, then the largest debtor repeatedly pays the
        # largest creditor. At most n - 1 payments; not always the fewest possible.
        if sum(b.values()) != 0:
            raise ValueError("Balances must sum to zero.")
        payments = []

        # Pair anyone who owes exactly what someone else is owed.
        unmatched = {}
        for pid in sorted(b):
            partners = unmatched.get(-b[pid])
            if partners:
                other = partners.pop(0)
                debtor, creditor = (pid, other) if b[pid] < 0 else (other, pid)
                payments.append((debtor, creditor, abs(b[pid])))
            else:
                unmatched.setdefault(b[pid], []).append(pid)
        rest = [pid for pids in unmatched.values() for pid in pids]

        # Max-heaps of (-amount, person_id); ties go to the smaller id so plans are stable.
        debtors = [(b[pid], pid) for pid in rest if b[pid] < 0]
        creditors = [(-b[pid], pid) for pid in rest if b[pid] > 0]
        heapq.heapify(debtors)
        heapq.heapify(creditors)

        while debtors and creditors:
            debt, d = heapq.heappop(debtors)
            credit, c = heapq.heappop(creditors)
            amount = min(-debt, -credit)
            payments.append((d, c, amount))
            if -debt > amount:
                heapq.heappush(debtors, (debt + amount, d))
            if -credit > amount:
                heapq.heappush(creditors, (credit + amount, c))

        paid = {pid: 0 for pid in b}
        received = {pid: 0 for pid in b}
        for d, c, amount in payments:
            paid[d] += amount
            received[c] += amount
        for pid in b:
            if b[pid] < 0 and paid[pid] != -b[pid]:
                raise RuntimeError(f"{pid} did not pay exactly what they owe.")
            if b[pid] > 0 and received[pid] != b[pid]:
                raise RuntimeError(f"{pid} did not receive exactly what they are owed.")
        return payments

    def record_settlement(self, from_person_id, to_person_id, amount_cents, payment_id,
                          created_at: datetime | None = None):
        # Call only after an actual off-app payment is confirmed.
        sender = self.get_member(from_person_id)
        recipient = self.get_member(to_person_id)
        if from_person_id == to_person_id:
            raise ValueError("A person cannot pay themselves.")
        if not isinstance(amount_cents, int) or amount_cents <= 0:
            raise ValueError("amount_cents must be a positive integer.")
        if any(expense.id == payment_id for expense in self.expenses):
            raise ValueError(f"Payment {payment_id} has already been recorded.")

        settlement = Expense(
            id=payment_id,
            paid_by=sender,
            amount_cents=amount_cents,
            description=f"Payment from {sender.name} to {recipient.name}",
            category=Category.SETTLEMENT,
            splits={from_person_id: amount_cents, to_person_id: -amount_cents},
            created_at=created_at,
        )
        self.add_expense(settlement)
        return settlement
