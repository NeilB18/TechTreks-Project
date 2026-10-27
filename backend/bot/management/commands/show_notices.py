from django.core.management.base import BaseCommand

from bot.models import PrivateNotice


class Command(BaseCommand):
    help = ("Print stored private messages (BOT_DM_MODE=store), newest last. For testing before sign-in works: "
            "these are private, so don't run it on a real group's trip without their OK.")

    def add_arguments(self, parser):
        parser.add_argument("trip_id")
        parser.add_argument("--person", help="only this person id")
        parser.add_argument("--last", type=int, default=20, help="how many (default 20)")

    def handle(self, trip_id, person, last, **_):
        notices = PrivateNotice.objects.filter(trip_id=trip_id)
        if person:
            notices = notices.filter(person_id=person)
        rows = list(notices.order_by("-created_at")[:last])[::-1]
        if not rows:
            self.stdout.write("No private messages stored.")
        for n in rows:
            self.stdout.write(f"[{n.created_at:%b %d %H:%M}] to {n.person_id}: {n.text}")
