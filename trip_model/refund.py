# class Refund:
#     id; expense_id; amount_cents
#     per_person: dict[person_id, int]   # same ratio as the expense's shares; sums to amount_cents
#     note; created_at
#     original_amount; currency          # as typed in chat; the MVP is USD-only
#
#     Made by Expense.add_refund(), which checks it against the expense.

from datetime import datetime

class Refund:
    def __init__(self, id, expense_id, amount_cents, per_person: dict, note="",
                 created_at: datetime | None = None, original_amount=None, currency="USD"):
        self.id = id
        self.expense_id = expense_id
        self.amount_cents = amount_cents
        self.per_person = per_person
        self.note = note
        self.created_at = created_at if created_at is not None else datetime.now()
        self.original_amount = original_amount if original_amount is not None else amount_cents
        self.currency = currency
