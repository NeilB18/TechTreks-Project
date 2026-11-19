"""The bot stops suggesting and looking up places (decided Nov 12, 2026).

- Activities lose their map check (lat, lon, verified) and kind, and get a slot (morning, lunch, ...).
  Plans already saved keep their clock times.
- The itinerary drafts table goes, and so do home_city and planning_notes.
- Lodging becomes plain text: the saved name and address ("Freehand Miami, 2727 Indian Creek Dr").
- Ideas lose their map details but keep their location.
- "itinerary_saves" leaves leader_approval: there are no drafts left to save.
"""

from django.db import migrations, models

IDEA_KEYS = ("idea_id", "name", "location", "est_cost_cents", "suggested_by")


def lodging_text(lodging) -> str | None:
    """"Freehand Miami, 2727 Indian Creek Dr": the name and the address, so the trip page's Maps link finds the
    exact place. Just one of them when that's all there is, or when the name already has the address in it."""
    if not isinstance(lodging, dict):
        return None
    name, address = (lodging.get("name") or "").strip(), (lodging.get("address") or "").strip()
    text = f"{name}, {address}" if name and address and address.lower() not in name.lower() else name or address
    return text[:200] or None


def forwards(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    for trip in Trip.objects.all():
        trip.lodging_text = lodging_text(trip.lodging)
        trip.ideas = [{k: i.get(k) for k in IDEA_KEYS if k != "location" or i.get("location")} for i in trip.ideas or []]
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
