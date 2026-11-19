from django.db import models

from trips.models import Trip


class GroupChat(models.Model):
    """A GroupMe group linked to a trip, and the bot that posts in it."""
    group_id = models.CharField(max_length=64, unique=True)
    bot_id = models.CharField(max_length=64)
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="group_chat")
    # The group's share link ("Invite friends"), for groups the site made with Add a trip.
    join_url = models.URLField(max_length=300, blank=True, default="")

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

