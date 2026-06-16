from django.contrib.gis.db import models as gis_models
from django.db import models

from apps.core.models import BaseModel
from apps.geodata.models import County, State


class AirQualityObservation(BaseModel):
    """
    Real-time primary AQI reading from the EPA AirNow API for a US reporting area.

    Only the *primary* pollutant (highest AQI) per reporting area is stored.
    Readings with AQI ≤ 50 (Good) are skipped at ingest; this table only
    contains Moderate or worse air quality events.

    Linked to State and County for efficient spatial filtering and joins.
    County may be NULL for multi-county or state-wide reporting areas.

    The `location` PointField mirrors `latitude`/`longitude` as a native
    PostGIS geometry, enabling ST_Contains, ST_DWithin, and spatial index
    queries on the AQ layer.
    """

    # AirNow reporting area name (e.g. "Los Angeles-South Coast Air Basin")
    reporting_area = models.CharField(max_length=200, db_index=True)

    # Foreign keys for structured lookups
    state = models.ForeignKey(
        State,
        related_name="air_quality_observations",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="US state this reading belongs to.",
    )
    county = models.ForeignKey(
        County,
        related_name="air_quality_observations",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Nearest county; may be NULL for multi-county reporting areas.",
    )

    # Location of the monitoring station / centroid of reporting area
    # Stored as both plain decimals (for simple display) and a PostGIS
    # PointField (for spatial queries, ST_DWithin, bbox filtering, etc.).
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location = gis_models.PointField(
        srid=4326,
        null=True,
        blank=True,
        help_text="PostGIS point geometry derived from latitude/longitude.",
    )

    # Observation time — AirNow updates hourly
    observed_at = models.DateTimeField(db_index=True)

    # Pollutant that is driving the primary (highest) AQI
    # Common values: 'PM2.5', 'PM10', 'O3', 'CO', 'SO2', 'NO2'
    pollutant = models.CharField(max_length=20)

    # AQI value (0–500 per EPA scale)
    aqi = models.IntegerField()

    # Human-readable EPA category label
    # 'Moderate', 'Unhealthy for Sensitive Groups', 'Unhealthy',
    # 'Very Unhealthy', 'Hazardous'
    aqi_category = models.CharField(max_length=60)

    class Meta:
        unique_together = [("reporting_area", "observed_at", "pollutant")]
        indexes = [
            models.Index(fields=["-aqi", "-observed_at"]),
            models.Index(fields=["state", "-observed_at"]),
            models.Index(fields=["county", "-observed_at"]),
        ]
        ordering = ["-aqi", "-observed_at"]
        verbose_name = "Air Quality Observation"
        verbose_name_plural = "Air Quality Observations"

    def __str__(self):
        return (
            f"[{self.aqi_category}] {self.reporting_area} "
            f"AQI {self.aqi} ({self.pollutant}) @ {self.observed_at:%Y-%m-%d %H:%M}"
        )
