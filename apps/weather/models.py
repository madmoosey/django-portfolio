from django.contrib.gis.db import models

from apps.core.models import BaseModel
from apps.geodata.models import County


class WeatherStation(BaseModel):
    """NOAA weather observation station."""

    station_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    location = models.PointField(srid=4326)
    county = models.ForeignKey(
        County, related_name="weather_stations", on_delete=models.SET_NULL, null=True, blank=True
    )
    elevation_m = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.station_id} - {self.name}"


class TemperatureObservation(BaseModel):
    """Daily temperature observation from a weather station."""

    station = models.ForeignKey(
        WeatherStation, related_name="observations", on_delete=models.CASCADE
    )
    date = models.DateField(db_index=True)
    tmax_celsius = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    tmin_celsius = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    tavg_celsius = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    precipitation_mm = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)

    class Meta:
        unique_together = ["station", "date"]
        indexes = [
            models.Index(fields=["date", "tmax_celsius"]),  # For heat wave queries
        ]

    def __str__(self):
        return f"{self.station.station_id} - {self.date}"
