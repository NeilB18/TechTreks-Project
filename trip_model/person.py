# class Person:
#     id; name; chat_user_id; payment_handle
#     budget: Budget | None       # their budget for this trip; everyone on the trip can see it
#     active: bool                # False once they drop out; they still owe their past splits
#     trips: list[Trip]

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .budget import Budget
    from .trip import Trip

class Person:
    def __init__(self, id, name, chat_user_id, payment_handle, budget: Budget | None = None,
                 active: bool = True):
        self.id = id
        self.name = name
        self.chat_user_id = chat_user_id
        self.payment_handle = payment_handle
        self.budget = budget
        self.active = active
        self.trips: list[Trip] = []
