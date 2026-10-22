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

from datetime import date

from activity import Activity
from category import Category
from expense import Expense
from person import Person
from poll import Poll
from reminder import Reminder
from trip_status import TripStatus

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
        return self._minimum_settlements(b)

    def _minimum_settlements(self, b: dict):
        # Exact minimum: split people into the most disjoint zero-sum groups, since n people
        # in k groups settle in n - k payments. Exponential in n; fine for small trip groups.
        ids = sorted(b)
        n = len(ids)
        if sum(b.values()) != 0:
            raise ValueError("Balances must sum to zero.")

        # sums[mask] = total balance of the people whose bits are set in mask
        sums = [0] * (1 << n)
        for mask in range(1, 1 << n):
            low_bit = mask & -mask
            sums[mask] = sums[mask ^ low_bit] + b[ids[low_bit.bit_length() - 1]]

        cache = {}

        def best_partition(remaining):
            if remaining == 0:
                return []
            if remaining in cache:
                return cache[remaining]

            anchor = remaining & -remaining
            others = remaining ^ anchor
            best = None
            sub = others
            while True:
                group = sub | anchor
                if sums[group] == 0:
                    rest = best_partition(remaining ^ group)
                    if rest is not None and (best is None or len(rest) + 1 > len(best)):
                        best = [group] + rest
                if sub == 0:
                    break
                sub = (sub - 1) & others
            cache[remaining] = best
            return best

        groups = best_partition((1 << n) - 1)
        payments = []

        for group in groups:
            members = [ids[i] for i in range(n) if group & (1 << i)]
            remaining_debt = {pid: -b[pid] for pid in members if b[pid] < 0}
            remaining_credit = {pid: b[pid] for pid in members if b[pid] > 0}
            debtors = list(remaining_debt)
            creditors = list(remaining_credit)

            # Transfers only between original debtors and original creditors.
            while debtors and creditors:
                d = debtors[0]
                c = creditors[0]
                amount = min(remaining_debt[d], remaining_credit[c])
                payments.append((d, c, amount))
                remaining_debt[d] -= amount
                remaining_credit[c] -= amount
                if remaining_debt[d] == 0:
                    debtors.pop(0)
                if remaining_credit[c] == 0:
                    creditors.pop(0)

        paid = {pid: 0 for pid in ids}
        received = {pid: 0 for pid in ids}
        for d, c, amount in payments:
            paid[d] += amount
            received[c] += amount
        for pid in ids:
            if b[pid] < 0 and paid[pid] != -b[pid]:
                raise RuntimeError(f"{pid} did not pay exactly what they owe.")
            if b[pid] > 0 and received[pid] != b[pid]:
                raise RuntimeError(f"{pid} did not receive exactly what they are owed.")
        if len(payments) != n - len(groups):
            raise RuntimeError("Settlement plan is not minimal.")
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
