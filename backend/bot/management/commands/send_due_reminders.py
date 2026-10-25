from django.core.management.base import BaseCommand
from django.utils import timezone

from agent.backend.core.engine import parse_time
from bot import groupme
from bot.models import GroupChat
from trips.models import Person, Reminder, Trip
from trips.services import load_trip


class Command(BaseCommand):
    help = "Send reminders whose due_at has passed. Run every few minutes from cron."

    def handle(self, **_):
        now = parse_time(timezone.now().isoformat(), "now")
        sent = 0
        for row in Trip.objects.filter(reminders__sent=False).distinct():
            chat = GroupChat.objects.filter(trip=row).first()
            if chat is None:
                continue
            for r in load_trip(row.id).reminders:
                if not r.is_due(now):
                    continue
                if r.audience == "all":
                    groupme.post_to_group(chat.bot_id, f"⏰ Reminder: {r.message}")
                else:
                    for person in Person.objects.filter(trip=row, person_id__in=[p.id for p in r.audience]):
                        groupme.send_dm(row, person, f"⏰ Reminder: {r.message}")
                # Only this flag changes, so a concurrent tool call on the trip isn't overwritten.
                Reminder.objects.filter(trip=row, reminder_id=r.id).update(sent=True)
                sent += 1
        self.stdout.write(f"Sent {sent} reminder(s).")
