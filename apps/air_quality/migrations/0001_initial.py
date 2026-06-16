"""
Initial migration for apps.air_quality.

Corrected to match BaseModel which uses:
  - id          = UUIDField (primary key)
  - created_at  = DateTimeField (auto_now_add, db_index)
  - updated_at  = DateTimeField (auto_now)
  - is_active   = BooleanField (default=True, db_index)
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("geodata", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AirQualityObservation",
            fields=[
                # --- BaseModel fields ---
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this record.",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        help_text="Timestamp when this record was created.",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="Timestamp when this record was last updated.",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        db_index=True,
                        help_text="Soft-delete flag.",
                    ),
                ),
                # --- AirQualityObservation fields ---
                ("reporting_area", models.CharField(db_index=True, max_length=200)),
                (
                    "state",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="air_quality_observations",
                        to="geodata.state",
                        help_text="US state this reading belongs to.",
                    ),
                ),
                (
                    "county",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="air_quality_observations",
                        to="geodata.county",
                        help_text="Nearest county; may be NULL for multi-county reporting areas.",
                    ),
                ),
                (
                    "latitude",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
                ),
                (
                    "longitude",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
                ),
                ("observed_at", models.DateTimeField(db_index=True)),
                ("pollutant", models.CharField(max_length=20)),
                ("aqi", models.IntegerField()),
                ("aqi_category", models.CharField(max_length=60)),
            ],
            options={
                "verbose_name": "Air Quality Observation",
                "verbose_name_plural": "Air Quality Observations",
                "ordering": ["-aqi", "-observed_at"],
                "abstract": False,
            },
        ),
        migrations.AlterUniqueTogether(
            name="airqualityobservation",
            unique_together={("reporting_area", "observed_at", "pollutant")},
        ),
        migrations.AddIndex(
            model_name="airqualityobservation",
            index=models.Index(fields=["-aqi", "-observed_at"], name="aq_aqi_obs_idx"),
        ),
        migrations.AddIndex(
            model_name="airqualityobservation",
            index=models.Index(fields=["state", "-observed_at"], name="aq_state_obs_idx"),
        ),
        migrations.AddIndex(
            model_name="airqualityobservation",
            index=models.Index(fields=["county", "-observed_at"], name="aq_county_obs_idx"),
        ),
    ]
