from django.core.management.base import BaseCommand
from django.utils import timezone

from bot import groupme
from bot.models import GroupChat
from trips.models import Person, Reminder


class Command(BaseCommand):
    help = "Send reminders whose due_at has passed. Run every few minutes from cron."

    def handle(self, **_):
        now = timezone.now().strftime("%Y-%m-%dT%H:%M")
        sent = 0
        for r in Reminder.objects.filter(sent=False).select_related("trip"):
            if r.due_at[:16] > now:  # ISO strings compare in time order
                continue
            chat = GroupChat.objects.filter(trip=r.trip).first()
            if chat is None:
                continue
            if r.audience == "all":
                groupme.post_to_group(chat.bot_id, f"⏰ Reminder: {r.message}")
            else:
                for person in Person.objects.filter(trip=r.trip, person_id__in=r.audience):
                    groupme.send_dm(r.trip, person, f"⏰ Reminder: {r.message}")
            r.sent = True
            r.save(update_fields=["sent"])
            sent += 1
        self.stdout.write(f"Sent {sent} reminder(s).")
