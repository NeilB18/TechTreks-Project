# class Activity:
#     id; name; location | None; start | None; end | None   # date or datetime
#     slot | None                    # "morning", "lunch", "afternoon", "dinner" or "night" when the group named one;
#                                    #   start is then just the day. None: a clock time, or just a day.
#     est_cost_cents | None; cost_is_per_person: bool        # False: est_cost_cents is the group total
#     attendees: list[Person]; important: bool; booking_url | None
#     expense_id | None              # links the plan to the real cost once someone pays
#     from_idea: bool                # came off the ideas list (goes back on it if removed)
#
#     est_per_person_cents() -> int | None
#     sort_key() -> (datetime, minutes)   # the day, then the clock time or slot; just-a-day plans first
#     update(**changes)              # edits, re-checking that it doesn't end before it starts

from datetime import date, datetime
from .person import Person

# Parts of the day the group can put a plan in, in order. Any number of plans can share one. The minutes are only
# for sorting a day: a plan in a slot has no clock time.
SLOTS = {"morning": 9 * 60, "lunch": 12 * 60, "afternoon": 15 * 60, "dinner": 19 * 60, "night": 22 * 60}

def as_datetime(value: date | datetime):
    # A plain date counts as the start of that day.
    return value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)

class Activity:
    def __init__(self, id, name, location=None, start: date | datetime | None = None,
                 end: date | datetime | None = None, est_cost_cents=None,
                 cost_is_per_person: bool = True, attendees: list[Person] | None = None,
                 important: bool = False, booking_url=None, expense_id=None, slot: str | None = None,
                 from_idea: bool = False):
        self.id = id
        self.name = name
        self.location = location
        self.start = start
        self.end = end
        self.slot = slot
        self.est_cost_cents = est_cost_cents
        self.cost_is_per_person = cost_is_per_person
        self.attendees = attendees if attendees is not None else []
        self.important = important
        self.booking_url = booking_url
        self.expense_id = expense_id
        self.from_idea = from_idea
        self._check_times()

    def _check_times(self):
        if self.start is not None and self.end is not None and as_datetime(self.end) < as_datetime(self.start):
            raise ValueError("Activity cannot end before it starts.")
        if self.slot is not None:
            if self.slot not in SLOTS:
                raise ValueError(f"slot must be one of {list(SLOTS)}")
            if not isinstance(self.start, date) or isinstance(self.start, datetime):
                raise ValueError("A plan in a slot needs a day and no clock time.")

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

    def sort_key(self):
        day = as_datetime(self.start)
        if isinstance(self.start, datetime):
            return day.replace(hour=0, minute=0, second=0, microsecond=0), self.start.hour * 60 + self.start.minute
        return day, SLOTS[self.slot] if self.slot else -1

    def est_per_person_cents(self):
        if self.est_cost_cents is None or self.cost_is_per_person or not self.attendees:
            return self.est_cost_cents
        return round(self.est_cost_cents / len(self.attendees))
