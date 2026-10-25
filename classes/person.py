# class Person:
#     id; name; chat_user_id; payment_handle
#     budget: Budget | None       # private to this person
#     trips: list[Trip]

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .budget import Budget
    from .trip import Trip

class Person:
    def __init__(self, id, name, chat_user_id, payment_handle, budget: Budget | None = None):
        self.id = id
        self.name = name
        self.chat_user_id = chat_user_id
        self.payment_handle = payment_handle
        self.budget = budget
        self.trips: list[Trip] = []
