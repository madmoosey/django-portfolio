"""
Data migration: backfill AirQualityObservation.location from latitude/longitude.

All rows that have non-null latitude/longitude but a null PostGIS location
(ingested before the save() override was added) are updated in a single
ST_SetSRID(ST_MakePoint(...)) SQL statement.

This is a one-shot data migration; future saves auto-populate location via
AirQualityObservation.save().
"""

from django.db import migrations


def backfill_location(apps, schema_editor):
    """
    UPDATE air_quality_airqualityobservation
    SET    location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    WHERE  location IS NULL
      AND  latitude  IS NOT NULL
      AND  longitude IS NOT NULL
    """
    schema_editor.execute(
        """
        UPDATE air_quality_airqualityobservation
        SET    location = ST_SetSRID(
                   ST_MakePoint(longitude::double precision,
                                latitude::double precision),
                   4326
               )
        WHERE  location  IS NULL
          AND  latitude  IS NOT NULL
          AND  longitude IS NOT NULL
        """
    )


def noop(apps, schema_editor):
    pass  # not reversible — PostGIS data can simply be regenerated


class Migration(migrations.Migration):

    dependencies = [
        (
            "air_quality",
            "0002_rename_aq_aqi_obs_idx_air_quality_aqi_960338_idx_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(backfill_location, reverse_code=noop),
    ]
