from django.db import models

from trips.models import Trip


class GroupChat(models.Model):
    """A GroupMe group linked to a trip, and the bot that posts in it."""
    group_id = models.CharField(max_length=64, unique=True)
    bot_id = models.CharField(max_length=64)
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="group_chat")

    def __str__(self):
        return f"GroupMe {self.group_id} -> {self.trip_id}"


class Conversation(models.Model):
    """The agent's message history for a trip (webhooks are stateless)."""
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="conversation")
    history = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)


class ProcessedMessage(models.Model):
    """GroupMe message ids already handled, so a re-delivered callback is ignored."""
    message_id = models.CharField(max_length=64, unique=True)
    received_at = models.DateTimeField(auto_now_add=True)


class PrivateNotice(models.Model):
    """A private message for one person, kept when it can't be sent as a GroupMe DM
    (BOT_DM_MODE=store). Shown to them after sign-in; never in the group."""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="private_notices")
    person_id = models.CharField(max_length=64)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
