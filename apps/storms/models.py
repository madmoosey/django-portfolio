from django.contrib.gis.db import models
from apps.core.models import BaseModel
from apps.geodata.models import State, County


class StormEvent(BaseModel):
    """NOAA Storm Events Database record."""

    event_id = models.CharField(max_length=50, unique=True, db_index=True)
    event_type = models.CharField(
        max_length=100, db_index=True
    )  # 'Tornado', 'Hurricane', 'Heat', etc.
    begin_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(null=True, blank=True)
    state = models.ForeignKey(State, related_name="storm_events", on_delete=models.CASCADE)
    county = models.ForeignKey(
        County, related_name="storm_events", on_delete=models.CASCADE, null=True, blank=True
    )
    begin_location = models.PointField(srid=4326, null=True, blank=True)
    end_location = models.PointField(srid=4326, null=True, blank=True)
    magnitude = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    magnitude_type = models.CharField(
        max_length=20, null=True, blank=True
    )  # 'EF' for tornadoes, 'kt' for hurricanes
    deaths_direct = models.IntegerField(default=0)
    injuries_direct = models.IntegerField(default=0)
    damage_property_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    damage_crops_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    episode_narrative = models.TextField(null=True, blank=True)
    event_narrative = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_type", "begin_date"]),
            models.Index(fields=["county", "event_type"]),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.begin_date.date()}"


class ActiveAlert(BaseModel):
    """Real-time NWS severe weather alert."""

    alert_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=50)  # 'Extreme', 'Severe', 'Moderate', 'Minor'
    urgency = models.CharField(max_length=50)
    certainty = models.CharField(max_length=50)
    headline = models.TextField()
    description = models.TextField()
    instruction = models.TextField(null=True, blank=True)
    effective = models.DateTimeField()
    expires = models.DateTimeField()
    affected_zones = models.JSONField(default=list)  # List of NWS zone codes
    geometry = models.MultiPolygonField(srid=4326, null=True, blank=True)

    def __str__(self):
        return f"[{self.severity}] {self.event_type} (expires {self.expires})"
