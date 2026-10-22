"""Database models. They mirror agent/backend/fake/models.py field for field.

All money is integer cents; expense and refund amounts are in the trip's base
currency, with the original amount, currency and FX rate kept alongside.
Rows within a trip keep their order through `position`.
"""

from django.conf import settings
from django.db import models


class Trip(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=16, default="PLANNING")
    destination = models.CharField(max_length=200, null=True, blank=True)
    start_date = models.CharField(max_length=10, null=True, blank=True)  # ISO date
    end_date = models.CharField(max_length=10, null=True, blank=True)
    target_break = models.CharField(max_length=100, null=True, blank=True)
    base_currency = models.CharField(max_length=3, default="USD")
    group_budget = models.IntegerField(null=True, blank=True)
    leader_id = models.CharField(max_length=64, null=True, blank=True)
    leader_approval = models.JSONField(default=list)
    auto_log_mode = models.CharField(max_length=32, null=True, blank=True)

    def __str__(self):
        return self.name


class Person(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="people")
    person_id = models.CharField(max_length=64)
    name = models.CharField(max_length=100)
    chat_user_id = models.CharField(max_length=100)
    payment_handle = models.CharField(max_length=100, null=True, blank=True)
    active = models.BooleanField(default=True)
    position = models.IntegerField(default=0)
    # The signed-in account that proved it owns this chat user (see accounts/services.py).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="trip_people")

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "person_id"], name="unique_person_per_trip"),
            models.UniqueConstraint(fields=["trip", "chat_user_id"], name="unique_chat_user_per_trip"),
        ]

    def __str__(self):
        return f"{self.name} ({self.trip_id})"


class Budget(models.Model):
    """Private. Only ever shown to its owner."""
    person = models.OneToOneField(Person, on_delete=models.CASCADE, related_name="budget")
    total_cents = models.IntegerField()
    limits = models.JSONField(default=dict)  # Category -> cents


class Exclusion(models.Model):
    """Category opt-out, e.g. (jake, DRINKS)."""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="exclusions")
    person_id = models.CharField(max_length=64)
    category = models.CharField(max_length=16)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["trip", "person_id", "category"], name="unique_opt_out")]


class Expense(models.Model):
    id = models.CharField(primary_key=True, max_length=32)  # globally unique, e.g. "e12"
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="expenses")
    paid_by = models.CharField(max_length=64)
    amount_cents = models.IntegerField()
    original_amount = models.IntegerField()
    original_currency = models.CharField(max_length=3)
    fx_rate = models.FloatField()
    description = models.CharField(max_length=300)
    category = models.CharField(max_length=16)
    created_at = models.CharField(max_length=32)
    source_message = models.TextField(blank=True, default="")
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class ExpenseSplit(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="splits")
    person_id = models.CharField(max_length=64)
    cents = models.IntegerField()
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class Refund(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="refunds")
    refund_id = models.CharField(max_length=32)
    expense_id = models.CharField(max_length=32)
    amount_cents = models.IntegerField()
    original_amount = models.IntegerField()
    currency = models.CharField(max_length=3)
    note = models.TextField(blank=True, default="")
    created_at = models.CharField(max_length=32)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class RefundShare(models.Model):
    refund = models.ForeignKey(Refund, on_delete=models.CASCADE, related_name="shares")
    person_id = models.CharField(max_length=64)
    cents = models.IntegerField()
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class Activity(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="activities")
    activity_id = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200, null=True, blank=True)
    start = models.CharField(max_length=32, null=True, blank=True)
    end = models.CharField(max_length=32, null=True, blank=True)
    est_cost_cents = models.IntegerField(null=True, blank=True)
    cost_is_per_person = models.BooleanField(default=True)
    attendees = models.JSONField(default=list)
    important = models.BooleanField(default=False)
    booking_url = models.URLField(max_length=500, null=True, blank=True)
    expense_id = models.CharField(max_length=32, null=True, blank=True)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class Poll(models.Model):
    id = models.CharField(primary_key=True, max_length=32)  # globally unique, e.g. "p3"
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="polls")
    question = models.CharField(max_length=300)
    options = models.JSONField(default=list)
    closes_at = models.CharField(max_length=32, null=True, blank=True)
    is_open = models.BooleanField(default=True)
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    person_id = models.CharField(max_length=64)
    option = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["poll", "person_id"], name="one_vote_per_person")]


class Reminder(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="reminders")
    reminder_id = models.CharField(max_length=32)
    message = models.TextField()
    due_at = models.CharField(max_length=32)
    audience = models.JSONField()  # list of person ids, or "all"
    sent = models.BooleanField(default=False)
    created_by = models.CharField(max_length=16, default="agent")
    position = models.IntegerField(default=0)

    class Meta:
        ordering = ["position"]


class ItineraryDraft(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="itinerary_drafts")
    draft_id = models.CharField(max_length=32)
    days = models.JSONField()
