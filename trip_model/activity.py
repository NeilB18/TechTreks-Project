# class Activity:
#     id; name; location | None; start | None; end | None   # date or datetime
#     est_cost_cents | None; cost_is_per_person: bool        # False: est_cost_cents is the group total
#     attendees: list[Person]; important: bool; booking_url | None
#     expense_id | None              # links the plan to the real cost once someone pays
#
#     est_per_person_cents() -> int | None
#     update(**changes)              # edits, re-checking that it doesn't end before it starts

from datetime import date, datetime
from .person import Person

def as_datetime(value: date | datetime):
    # A plain date counts as the start of that day.
    return value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)

class Activity:
    def __init__(self, id, name, location=None, start: date | datetime | None = None,
                 end: date | datetime | None = None, est_cost_cents=None,
                 cost_is_per_person: bool = True, attendees: list[Person] | None = None,
                 important: bool = False, booking_url=None, expense_id=None):
        self.id = id
        self.name = name
        self.location = location
        self.start = start
        self.end = end
        self.est_cost_cents = est_cost_cents
        self.cost_is_per_person = cost_is_per_person
        self.attendees = attendees if attendees is not None else []
        self.important = important
        self.booking_url = booking_url
        self.expense_id = expense_id
        self._check_times()

    def _check_times(self):
        if self.start is not None and self.end is not None and as_datetime(self.end) < as_datetime(self.start):
            raise ValueError("Activity cannot end before it starts.")

    def update(self, **changes):
        old = {field: getattr(self, field) for field in changes}
        for field, value in changes.items():
            setattr(self, field, value)
        try:
            self._check_times()
        except ValueError:
            for field, value in old.items():
                setattr(self, field, value)
            raise

    def est_per_person_cents(self):
        if self.est_cost_cents is None or self.cost_is_per_person or not self.attendees:
            return self.est_cost_cents
        return round(self.est_cost_cents / len(self.attendees))
