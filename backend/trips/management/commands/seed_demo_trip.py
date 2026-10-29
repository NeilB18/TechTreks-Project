"""Create a sample trip through the same backend used by the bot, without overwriting a trip."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from scripts.export_fixtures import demo
from trips.models import Trip
from trips.services import DjangoBackend


class Command(BaseCommand):
    help = "Create a sample Miami trip with members, activities, expenses, a refund, and a payback."

    def add_arguments(self, parser):
        parser.add_argument("--trip-id", default="supabase-demo")

    def handle(self, *args, **options):
        trip_id = options["trip_id"]
        if not trip_id or len(trip_id) > 64 or not all(c.isascii() and (c.isalnum() or c in "_-") for c in trip_id):
            raise CommandError("Trip ID must be 1–64 letters, numbers, underscores, or hyphens.")
        with transaction.atomic():
            if Trip.objects.filter(pk=trip_id).exists():
                self.stdout.write(f"Trip {trip_id} already exists; left unchanged.")
                return
            data = demo(DjangoBackend(), trip_id=trip_id)
        detail = data["detail"]
        self.stdout.write(self.style.SUCCESS(
            f"Created {trip_id}: {len(detail['members'])} members, "
            f"{len(detail['activities'])} activities, {len(detail['expenses'])} expense records. "
            f"Open /trips/{trip_id}. All data and payment handles are sample values."
        ))
