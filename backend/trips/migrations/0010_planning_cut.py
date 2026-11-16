"""The bot stops suggesting and looking up places (decided Nov 12, 2026).

- Activities lose their map check (lat, lon, verified) and kind, and get a slot (morning, lunch, ...).
  Plans already saved keep their clock times.
- The itinerary drafts table goes, and so do home_city and planning_notes.
- Lodging becomes plain text: what the group wrote (the saved name).
- Ideas lose their map details.
- "itinerary_saves" leaves leader_approval: there are no drafts left to save.
"""

from django.db import migrations, models

IDEA_KEYS = ("idea_id", "name", "est_cost_cents", "suggested_by")


def forwards(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    for trip in Trip.objects.all():
        lodging = trip.lodging if isinstance(trip.lodging, dict) else None
        trip.lodging_text = ((lodging.get("name") or lodging.get("address") or "")[:200] or None) if lodging else None
        trip.ideas = [{k: i.get(k) for k in IDEA_KEYS} for i in trip.ideas or []]
        trip.leader_approval = [a for a in trip.leader_approval or [] if a != "itinerary_saves"]
        trip.save(update_fields=["lodging_text", "ideas", "leader_approval"])


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0009_trip_theme"),
    ]

    operations = [
        migrations.AddField(
            model_name="trip",
            name="lodging_text",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        # Not reversible: the map details are gone once this runs.
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(model_name="trip", name="lodging"),
        migrations.RenameField(model_name="trip", old_name="lodging_text", new_name="lodging"),
        migrations.RemoveField(model_name="trip", name="home_city"),
        migrations.RemoveField(model_name="trip", name="planning_notes"),
        migrations.RemoveField(model_name="activity", name="lat"),
        migrations.RemoveField(model_name="activity", name="lon"),
        migrations.RemoveField(model_name="activity", name="verified"),
        migrations.RemoveField(model_name="activity", name="kind"),
        migrations.AddField(
            model_name="activity",
            name="slot",
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
        migrations.DeleteModel(name="ItineraryDraft"),
    ]
