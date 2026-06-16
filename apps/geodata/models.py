"""
ArborWatch Geodata Models.

PostGIS models for US states and counties.
"""

from django.contrib.gis.db import models

from apps.core.models import BaseModel


class State(BaseModel):
    """US state boundaries with PostGIS geometries."""

    fips_code = models.CharField(
        max_length=2,
        unique=True,
        db_index=True,
        help_text="2-digit FIPS code (e.g. '06' for California)",
    )
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=2)

    # Using MultiPolygon instead of Polygon to support states like Hawaii with multiple islands
    geometry = models.MultiPolygonField(srid=4326)

    area_sq_km = models.DecimalField(
        max_digits=15, decimal_places=2, help_text="Total area in square kilometers"
    )
    population = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class County(BaseModel):
    """US county boundaries with PostGIS geometries."""

    fips_code = models.CharField(
        max_length=5,
        unique=True,
        db_index=True,
        help_text="5-digit FIPS code (State FIPS + County FIPS)",
    )
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="counties")

    geometry = models.MultiPolygonField(srid=4326)

    # Pre-simplified geometry (tolerance=0.01°, ~1 km) for the choropleth overlay.
    # Populated by the build_choropleth_cache management command after each ingest.
    # Eliminates the per-request ST_SimplifyPreserveTopology cost (~80 % of query time).
    simplified_geometry = models.MultiPolygonField(
        srid=4326,
        null=True,
        blank=True,
        help_text="Pre-simplified geometry for the choropleth endpoint (tolerance=0.01°).",
    )

    area_sq_km = models.DecimalField(
        max_digits=15, decimal_places=2, help_text="Total area in square kilometers"
    )
    population = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["state__name", "name"]
        verbose_name_plural = "counties"

    def __str__(self):
        return f"{self.name}, {self.state.abbreviation}"
