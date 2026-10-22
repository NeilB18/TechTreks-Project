# class Expense:
#     id; paid_by: Person; amount_cents; description; category
#     splits: dict[person_id, int]   # NET balance DELTAS, not amounts owed
#     created_at; source_message     # original chat text, useful for debugging the agent
#
#     Positive: this person is owed money. Negative: this person owes money.
#     Must satisfy sum(splits.values()) == 0.
#
#     split_equal(participant_ids) / split_custom(shares_cents) / split_percentage(percents)
#         -> update splits via _calculate_net_splits(shares_cents)

from __future__ import annotations
from datetime import datetime
from fractions import Fraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from category import Category
    from person import Person

class Expense:
    def __init__(self, id, paid_by: Person, amount_cents, description, category: Category,
                 splits: dict | None = None, created_at: datetime | None = None,
                 source_message=None):
        self.id = id
        self.paid_by = paid_by
        self.amount_cents = amount_cents
        self.description = description
        self.category = category
        self.splits = splits if splits is not None else {}
        self.created_at = created_at if created_at is not None else datetime.now()
        self.source_message = source_message

    def share_of(self, person_id):
        # delta = amount_paid - share_owed, so share_owed = amount_paid - delta
        paid = self.amount_cents if self.paid_by.id == person_id else 0
        return paid - self.splits.get(person_id, 0)

    def split_equal(self, participant_ids: list):
        if not participant_ids:
            raise ValueError("Need at least one participant.")
        if len(set(participant_ids)) != len(participant_ids):
            raise ValueError("Duplicate participant IDs.")

        count = len(participant_ids)
        base = self.amount_cents // count
        remainder = self.amount_cents % count
        shares = {}
        for i, person_id in enumerate(sorted(participant_ids)):
            shares[person_id] = base + (1 if i < remainder else 0)
        return self._calculate_net_splits(shares)

    def split_custom(self, shares_cents: dict):
        # Explicit allocation of the *entire* bill, including the payer's share if any.
        return self._calculate_net_splits(shares_cents)

    def split_percentage(self, percents: dict):
        # str() first so floats like 33.33 are read as the decimal the caller meant
        exact_percents = {person_id: Fraction(str(p)) for person_id, p in percents.items()}
        if any(p < 0 for p in exact_percents.values()):
            raise ValueError("Percentages must be >= 0.")
        if sum(exact_percents.values()) != 100:
            raise ValueError("Percentages must sum to 100.")

        exact_shares = {person_id: self.amount_cents * p / 100
                        for person_id, p in exact_percents.items()}
        shares = {person_id: int(share) for person_id, share in exact_shares.items()}
        leftover = self.amount_cents - sum(shares.values())

        # Largest fractional remainder first; ties broken by stable ID order.
        by_remainder = sorted(sorted(exact_shares),
                              key=lambda person_id: exact_shares[person_id] - shares[person_id],
                              reverse=True)
        for person_id in by_remainder[:leftover]:
            shares[person_id] += 1
        return self._calculate_net_splits(shares)

    def _calculate_net_splits(self, shares_cents: dict):
        if not isinstance(self.amount_cents, int) or self.amount_cents < 0:
            raise ValueError("amount_cents must be a non-negative integer.")
        if self.paid_by is None or self.paid_by.id is None:
            raise ValueError("Expense needs a valid payer.")
        if any(person_id is None for person_id in shares_cents):
            raise ValueError("Participant IDs must be valid.")
        if any(not isinstance(share, int) or share < 0 for share in shares_cents.values()):
            raise ValueError("Shares must be non-negative integer cents.")
        if sum(shares_cents.values()) != self.amount_cents:
            raise ValueError("Shares must add up to the full expense amount.")

        deltas = {person_id: -share for person_id, share in shares_cents.items()}
        deltas[self.paid_by.id] = deltas.get(self.paid_by.id, 0) + self.amount_cents
        deltas = {person_id: delta for person_id, delta in deltas.items() if delta != 0}

        if sum(deltas.values()) != 0:
            raise ValueError("Splits must sum to zero.")
        self.splits = deltas
        return deltas
