# class Trip:
#     id; name; status (PLANNING / BOOKED / ACTIVE / DONE)
#     destination | None; start_date | None; end_date | None   # empty until a poll decides them
#     target_break | None            # "spring break", "fall break", etc.
#     members: list[Person]; activities; expenses; polls; reminders
#
#     add_member(); add_expense(); add_activity(); add_poll(); add_reminder()
#     itinerary_by_day() -> dict[date, list[Activity]]
#     spent_by_category(person=None) -> dict[Category, int]
#     balances() -> dict[person_id, int]
#     settlement_plan() -> list[(from_person_id, to_person_id, amount_cents)]   # suggestion only
#     record_settlement(from_person_id, to_person_id, amount_cents, payment_id)

import heapq
from datetime import date

from .activity import Activity
from .category import Category
from .expense import Expense
from .person import Person
from .poll import Poll
from .reminder import Reminder
from .trip_status import TripStatus

class Trip:
    def __init__(self, id, name, status: TripStatus = TripStatus.PLANNING,
                 destination=None, start_date: date | None = None,
                 end_date: date | None = None, target_break=None):
        self.id = id
        self.name = name
        self.status = status
        self.destination = destination
        self.start_date = start_date
        self.end_date = end_date
        self.target_break = target_break
        self.members: list[Person] = []
        self.activities: list[Activity] = []
        self.expenses: list[Expense] = []
        self.polls: list[Poll] = []
        self.reminders: list[Reminder] = []

    def member_ids(self):
        return {member.id for member in self.members}

    def get_member(self, person_id):
        for member in self.members:
            if member.id == person_id:
                return member
        raise ValueError(f"Person {person_id} is not on this trip.")

    def add_member(self, person: Person):
        if person.id in self.member_ids():
            return
        self.members.append(person)
        if self not in person.trips:
            person.trips.append(self)

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
        itinerary = {}
        for activity in sorted(self.activities, key=lambda a: a.start):
            itinerary.setdefault(activity.start.date(), []).append(activity)
        return itinerary

    def spent_by_category(self, person: Person | None = None):
        # Whole-group spending, or just this person's shares. Settlements are not spending.
        spent = {category: 0 for category in Category if category != Category.SETTLEMENT}
        for expense in self.expenses:
            if expense.category == Category.SETTLEMENT:
                continue
            if person is None:
                spent[expense.category] += expense.amount_cents
            else:
                spent[expense.category] += expense.share_of(person.id)
        return spent

    def balances(self):
        balance = {member.id: 0 for member in self.members}
        for expense in self.expenses:
            for person_id, delta in expense.splits.items():
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

    def record_settlement(self, from_person_id, to_person_id, amount_cents, payment_id):
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
        )
        self.add_expense(settlement)
        return settlement
