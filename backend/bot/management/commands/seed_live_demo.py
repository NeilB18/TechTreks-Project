"""Build a full demo trip from a live trip's real members, and point its GroupMe group at it.

    manage.py seed_live_demo                     # test-trip's members -> demo-trip, group relinked
    manage.py seed_live_demo --reset             # rebuild demo-trip from scratch
    manage.py seed_live_demo --unlink            # point the group back at test-trip

The members keep their GroupMe ids and signed-in accounts, so the bot knows who's talking and the
trip page shows each person their own budget. Payment handles and amounts are sample values.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bot.models import GroupChat
from trips.models import Person, Trip
from trips.services import DjangoBackend

# Sample handles for the people we know; anyone else gets @<first name>-venmo.
HANDLES = {"romir_basu": "@romir-venmo", "roger_peng": "@roger-venmo", "neil_bhattacharyya": "neil@example.com"}


class Command(BaseCommand):
    help = "Create a demo trip full of sample data from a live trip's members, and link its GroupMe group to it."

    def add_arguments(self, parser):
        parser.add_argument("--source", default="test-trip", help="Live trip whose members and group to use")
        parser.add_argument("--trip-id", default="demo-trip")
        parser.add_argument("--reset", action="store_true", help="Delete and rebuild the demo trip if it exists")
        parser.add_argument("--unlink", action="store_true", help="Point the group back at the source trip and stop")

    def handle(self, source, trip_id, reset, unlink, **_):
        chat = GroupChat.objects.filter(trip_id__in=[source, trip_id]).first()
        if unlink:
            if not chat:
                raise CommandError("No GroupMe group is linked to either trip.")
            chat.trip_id = source
            chat.save()
            self.stdout.write(f"GroupMe group {chat.group_id} talks to {source!r} again.")
            return
        people = list(Person.objects.filter(trip_id=source, active=True))
        if not people:
            raise CommandError(f"Trip {source!r} has no members to copy.")
        with transaction.atomic():
            if Trip.objects.filter(pk=trip_id).exists():
                if not reset:
                    raise CommandError(f"{trip_id!r} already exists. Use --reset to rebuild it.")
                if chat and chat.trip_id == trip_id:
                    chat.trip_id = source
                    chat.save()
                Trip.objects.filter(pk=trip_id).delete()
            ids = self._seed(trip_id, people)
            for p in people:  # keep sign-in links, so "My budget" works for linked accounts
                Person.objects.filter(trip_id=trip_id, person_id=p.person_id).update(user=p.user)
            if chat:
                chat.trip_id = trip_id
                chat.save()
        group = f"GroupMe group {chat.group_id} now talks to it" if chat else "no GroupMe group to link"
        self.stdout.write(self.style.SUCCESS(
            f"Created {trip_id!r} with {len(ids)} members ({', '.join(ids)}); {group}. "
            f"Open /trips/{trip_id}. Undo the link with --unlink."))

    def _seed(self, t: str, people: list[Person]) -> list[str]:
        b = DjangoBackend()
        ids = [p.person_id for p in people]
        lead = ids[0]
        b.load_seed({
            "trip": {"id": t, "name": "Miami Spring Break", "status": "BOOKED", "destination": "Miami",
                     "start_date": "2027-03-14", "end_date": "2027-03-18", "base_currency": "USD",
                     "group_budget": 120000, "leader": lead,
                     "leader_approval": ["member_changes", "trip_changes"]},
            "members": [{"id": p.person_id, "name": p.name, "chat_user_id": p.chat_user_id,
                         "handle": HANDLES.get(p.person_id, f"@{p.person_id.split('_')[0]}-venmo")}
                        for p in people],
        })
        # Budgets: everyone has one; the leader's drinks limit is tight so a live "$90 round" sets off a warning.
        totals = [150000, 120000, 90000, 110000]
        for i, pid in enumerate(ids):
            limits = {"FOOD": 30000, "DRINKS": 10000} if pid == lead else {"FOOD": 25000}
            b.set_budget(trip_id=t, person_id=pid, total=totals[i % len(totals)], limits=limits)
        if len(ids) > 2:
            b.set_exclusion(trip_id=t, person_id=ids[2], category="DRINKS")  # a non-drinker, for opt-outs

        draft = b.generate_itinerary(trip_id=t, constraints="beach, food, one night out")["draft_id"]
        b.generate_itinerary(trip_id=t, save_draft_id=draft)
        b.add_activity(trip_id=t, name="Boat tour", location="Miami Beach Marina", start="2027-03-15T14:00",
                       est_cost_cents=60000, cost_is_per_person=False, important=True)

        log = dict(trip_id=t, currency="USD")
        second, third = ids[1 % len(ids)], ids[2 % len(ids)]
        b.log_expense(**log, paid_by=lead, amount=120000, description="Airbnb (Mar 14–18)",
                      category="LODGING", split_with=ids)
        b.log_expense(**log, paid_by=second, amount=4500, description="Uber from the airport",
                      category="TRANSPORT", split_with=ids)
        b.log_expense(**log, paid_by=third, amount=9000, description="Groceries", category="FOOD",
                      split_with=ids)
        b.log_expense(**log, paid_by=second, amount=18000, description="Dinner at Joe's", category="FOOD",
                      split_with=ids)
        b.log_expense(**log, paid_by=lead, amount=9000, description="Bar tab", category="DRINKS",
                      split_with=ids)
        b.log_expense(**log, paid_by=third, amount=30000, description="Jet skis", category="ACTIVITIES",
                      split_with=[second, third])
        concert = b.log_expense(**log, paid_by=lead, amount=24000, description="Concert tickets",
                                category="ACTIVITIES", split_with=ids)["expense_id"]
        b.record_refund(expense_id=concert, amount=6000, currency="USD", note="One ticket resold")
        if third != lead:
            b.record_payback(trip_id=t, from_person=third, to_person=lead, amount=20000, currency="USD")

        poll = b.create_poll(trip_id=t, question="Sunday dinner: Cuban or sushi?", options=["Cuban", "Sushi"],
                             closes_at="2027-03-12T20:00")["poll_id"]
        b.vote_poll(poll_id=poll, person_id=lead, option="Cuban")
        b.create_reminder(trip_id=t, message="Check in for flights and pack sunscreen",
                          due_at="2027-03-13T18:00", audience="all")
        return ids
