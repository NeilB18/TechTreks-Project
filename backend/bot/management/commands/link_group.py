from django.core.management.base import BaseCommand

from bot.models import GroupChat
from trips.models import Trip


class Command(BaseCommand):
    help = "Link a GroupMe group (and the bot added to it) to a trip, creating the trip if needed."

    def add_arguments(self, parser):
        parser.add_argument("group_id", help="GroupMe group id")
        parser.add_argument("bot_id", help="GroupMe bot id (dev.groupme.com/bots)")
        parser.add_argument("trip_id", help="Short trip id, e.g. miami-2027")
        parser.add_argument("--name", help="Trip name for a new trip", default=None)

    def handle(self, group_id, bot_id, trip_id, name, **_):
        trip, created = Trip.objects.get_or_create(id=trip_id, defaults={"name": name or trip_id})
        GroupChat.objects.update_or_create(group_id=group_id, defaults={"bot_id": bot_id, "trip": trip})
        what = "Created trip" if created else "Using existing trip"
        self.stdout.write(f"{what} {trip.id!r}; GroupMe group {group_id} now talks to it.")
        self.stdout.write("People are added to the trip the first time they @mention the bot.")
