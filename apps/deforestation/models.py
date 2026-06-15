from django.contrib.gis.db import models
from apps.core.models import BaseModel
from apps.geodata.models import County

class TreeCoverBaseline(BaseModel):
    """Baseline tree cover percentage for a geographic area in a given year."""
    county = models.ForeignKey(County, related_name='tree_cover_baselines', on_delete=models.CASCADE)
    year = models.IntegerField(db_index=True)
    tree_cover_percent = models.DecimalField(max_digits=5, decimal_places=2)
    tree_cover_area_ha = models.DecimalField(max_digits=12, decimal_places=2)
    data_source = models.CharField(max_length=50)  # 'GFW' or 'NLCD'
    raw_payload = models.JSONField(null=True, blank=True)  # Original API response for audit

    class Meta:
        unique_together = ['county', 'year', 'data_source']
        ordering = ['-year', 'county__name']

    def __str__(self):
        return f"{self.county.name} - {self.year} ({self.data_source})"

class TreeCoverLoss(BaseModel):
    """Annual tree cover loss for a geographic area."""
    county = models.ForeignKey(County, related_name='tree_cover_losses', on_delete=models.CASCADE)
    year = models.IntegerField(db_index=True)
    loss_area_ha = models.DecimalField(max_digits=12, decimal_places=2)
    loss_percent = models.DecimalField(max_digits=5, decimal_places=2)
    primary_driver = models.CharField(max_length=100, null=True, blank=True)  # fire, urbanization, etc.
    data_source = models.CharField(max_length=50)
    raw_payload = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ['county', 'year', 'data_source']
        ordering = ['-year', 'county__name']

    def __str__(self):
        return f"Loss {self.county.name} - {self.year}"

class DeforestationAlert(BaseModel):
    """Near-real-time deforestation alert from GLAD/RADD."""
    alert_date = models.DateField(db_index=True)
    confidence = models.CharField(max_length=20)  # 'high', 'nominal'
    location = models.PointField(srid=4326)
    county = models.ForeignKey(County, related_name='deforestation_alerts', on_delete=models.CASCADE, null=True, blank=True)
    alert_type = models.CharField(max_length=50)  # 'GLAD', 'RADD'
    area_ha = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-alert_date']

    def __str__(self):
        return f"{self.alert_type} Alert ({self.alert_date})"
