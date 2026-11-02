import logging
import time

from django.core.management.base import BaseCommand

from agent.backend.core.engine import parse_time
from bot import groupme
from bot.models import GroupChat
from bot.services import local_now
from trips.models import Person, Reminder, Trip
from trips.services import load_trip

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ("Send reminders whose due_at has passed (in BOT_TIME_ZONE). Run every few minutes from cron, "
            "or keep it running with --every 60.")

    def add_arguments(self, parser):
        parser.add_argument("--every", type=int, default=0, help="check again every N seconds instead of exiting")

    def handle(self, every, **_):
        while True:
            self.stdout.write(f"Sent {self.send_due()} reminder(s).")
            if not every:
                return
            time.sleep(every)

    def send_due(self) -> int:
        now = parse_time(local_now(), "now")
        sent = 0
        for row in Trip.objects.filter(reminders__sent=False).distinct():
            chat = GroupChat.objects.filter(trip=row).first()
            if chat is None:
                continue
            for r in load_trip(row.id).reminders:
                if not r.is_due(now):
                    continue
                # Everything goes to the group; a reminder for some people tags them.
                if r.audience == "all":
                    text = f"⏰ Reminder: {r.message}"
                else:
                    names = Person.objects.filter(trip=row, person_id__in=[p.id for p in r.audience]) \
                        .order_by("person_id").values_list("name", flat=True)
                    text = f"⏰ Reminder for {', '.join('@' + n for n in names)}: {r.message}"
                try:
                    groupme.post_to_group(chat.bot_id, text)
                except Exception:
                    # Left unsent, so the next run tries again; one failure doesn't block the others.
                    log.exception("Couldn't send reminder %s on trip %s", r.id, row.id)
                    continue
                # Only this flag changes, so a concurrent tool call on the trip isn't overwritten.
                Reminder.objects.filter(trip=row, reminder_id=r.id).update(sent=True)
                sent += 1
        return sent
