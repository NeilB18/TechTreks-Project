"""A share_token for each trip, the trip page's address.

Three steps: adding a unique column with a generated default in one go would give every
existing trip the same token (Django works the default out once per migration).
"""

from django.db import migrations, models

import trips.models


def fill_tokens(apps, schema_editor):
    Trip = apps.get_model("trips", "Trip")
    used = set()
    for trip in Trip.objects.filter(share_token__isnull=True):
        token = trips.models.new_share_token()
        while token in used:
            token = trips.models.new_share_token()
        used.add(token)
        trip.share_token = token
        trip.save(update_fields=["share_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("trips", "0007_trip_home_city"),
    ]

    operations = [
        migrations.AddField(
            model_name="trip",
            name="share_token",
            field=models.CharField(max_length=16, null=True),
        ),
        migrations.RunPython(fill_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="trip",
            name="share_token",
            field=models.CharField(default=trips.models.new_share_token, max_length=16, unique=True),
        ),
    ]
