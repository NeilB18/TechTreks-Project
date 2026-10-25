# class Activity:
#     id; name; location; start: datetime; end: datetime
#     est_cost_cents; cost_is_per_person: bool
#     attendees: list[Person]; important: bool; booking_url
#     expense_id | None              # links the plan to the real cost once someone pays

from datetime import datetime
from .person import Person

class Activity:
    def __init__(self, id, name, location, start: datetime, end: datetime,
                 est_cost_cents, cost_is_per_person: bool,
                 attendees: list[Person], important: bool, booking_url,
                 expense_id=None):
        if end < start:
            raise ValueError("Activity cannot end before it starts.")
        self.id = id
        self.name = name
        self.location = location
        self.start = start
        self.end = end
        self.est_cost_cents = est_cost_cents
        self.cost_is_per_person = cost_is_per_person
        self.attendees = attendees
        self.important = important
        self.booking_url = booking_url
        self.expense_id = expense_id
