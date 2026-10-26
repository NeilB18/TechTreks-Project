# class Budget:
#     owner_id; total_cents
#     limits: dict[Category, int]                       # e.g. {DRINKS: 8000}
#     remaining(category, expenses) -> int | None       # None if the category has no limit
#     warning(category, expenses, planned_cents=0) -> bool
#         # remaining minus planned (unpaid) costs < 10% of the category limit

from __future__ import annotations
from typing import TYPE_CHECKING

from .category import Category

if TYPE_CHECKING:
    from .expense import Expense

class Budget:
    def __init__(self, owner_id, total_cents, limits: dict[Category, int] | None = None):
        self.owner_id = owner_id
        self.total_cents = total_cents
        self.limits = limits if limits is not None else {}

    def spent(self, category, expenses: list[Expense]):
        # Settlements move debt around; they are not spending.
        if category == Category.SETTLEMENT:
            return 0
        return sum(expense.share_of(self.owner_id)
                   for expense in expenses if expense.category == category)

    def remaining(self, category, expenses: list[Expense]):
        if category not in self.limits:
            return None
        return self.limits[category] - self.spent(category, expenses)

    def warning(self, category, expenses: list[Expense], planned_cents=0):
        # planned_cents: this owner's share of activities that are planned but not paid yet.
        # Only category limits warn; the total is informational.
        remaining = self.remaining(category, expenses)
        if remaining is None:
            return False
        return remaining - planned_cents < 0.10 * self.limits[category]
