# class Reminder:
#     message; due_at; audience: list[Person] | "all"
#     sent: bool; created_by: "agent" | "system"

from datetime import datetime
from .person import Person

class Reminder:
    def __init__(self, message, due_at: datetime, audience: list[Person] | str = "all",
                 sent: bool = False, created_by: str = "system"):
        if isinstance(audience, str) and audience != "all":
            raise ValueError('audience must be a list of people or "all".')
        if created_by not in ("agent", "system"):
            raise ValueError('created_by must be "agent" or "system".')
        self.message = message
        self.due_at = due_at
        self.audience = audience
        self.sent = sent
        self.created_by = created_by

    def is_due(self, now: datetime | None = None):
        now = now if now is not None else datetime.now()
        return not self.sent and now >= self.due_at

    def mark_sent(self):
        self.sent = True
