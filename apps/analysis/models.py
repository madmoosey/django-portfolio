from django.db import models

from apps.core.models import BaseModel
from apps.geodata.models import County


class CountyRiskScore(BaseModel):
    """Computed risk score for a county."""

    county = models.ForeignKey(County, related_name="risk_scores", on_delete=models.CASCADE)
    risk_type = models.CharField(max_length=50)  # 'heat_wave', 'hurricane', 'tornado'
    score = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    confidence = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    computed_at = models.DateTimeField()
    factors = models.JSONField(
        default=dict
    )  # Breakdown: {"tree_loss": 28.5, "historical_freq": 22.0, ...}
    data_window_start = models.DateField()
    data_window_end = models.DateField()

    class Meta:
        unique_together = ["county", "risk_type", "computed_at"]
        indexes = [
            models.Index(fields=["risk_type", "score"]),
            models.Index(fields=["county", "risk_type", "-computed_at"]),
        ]

    def __str__(self):
        return f"{self.county.name} - {self.risk_type} Score: {self.score}"


class RiskTrend(BaseModel):
    """Time-series of risk score changes for trend analysis."""

    county = models.ForeignKey(County, related_name="risk_trends", on_delete=models.CASCADE)
    risk_type = models.CharField(max_length=50)
    month = models.DateField()  # First of month
    avg_score = models.DecimalField(max_digits=5, decimal_places=2)
    delta_from_previous = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ["county", "risk_type", "month"]

    def __str__(self):
        return f"{self.county.name} - {self.risk_type} Trend ({self.month})"


class MLModel(BaseModel):
    """Model registry for ML models."""

    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    risk_type = models.CharField(max_length=50)
    is_active = models.BooleanField(default=False)
    hyperparameters = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)
    s3_path = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together = ["name", "version"]

    def __str__(self):
        return f"{self.name} v{self.version} ({'Active' if self.is_active else 'Inactive'})"


class FeatureSnapshot(BaseModel):
    """Snapshot of features for a county at a specific time."""

    county = models.ForeignKey(County, on_delete=models.CASCADE)
    snapshot_date = models.DateField()
    features = models.JSONField(default=dict)

    class Meta:
        unique_together = ["county", "snapshot_date"]
