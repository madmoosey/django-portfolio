"""
Migration: add County.simplified_geometry for choropleth performance.

Adds a nullable MultiPolygonField that stores the pre-simplified (tolerance=0.01°)
county geometry used by the /counties/choropleth/ endpoint.

Populate after migrating with:
    python manage.py build_choropleth_cache
"""

import django.contrib.gis.db.models.fields
from django.contrib.gis.db import models


class Migration(django.db.migrations.Migration):

    dependencies = [
        ("geodata", "0002_alter_county_area_sq_km_alter_state_area_sq_km"),
    ]

    operations = [
        django.db.migrations.AddField(
            model_name="county",
            name="simplified_geometry",
            field=django.contrib.gis.db.models.fields.MultiPolygonField(
                blank=True,
                help_text="Pre-simplified geometry for the choropleth endpoint (tolerance=0.01°).",
                null=True,
                srid=4326,
            ),
        ),
    ]
