"""
Air quality feature extractor for the ML risk pipeline.

Aggregates the last 30 days of AirQualityObservation records for a county
into a flat feature dict compatible with both the rule-based scorer and
the XGBoost feature matrix.
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# Feature names — must stay stable across training and inference
AQ_FEATURE_COLS = [
    "aq_obs_count",
    "aq_max_aqi",
    "aq_mean_aqi",
    "aq_unhealthy_days",
    "aq_pm25_fraction",
]


class AirQualityFeatureExtractor:
    """Extract 30-day AQ statistics per county."""

    def extract(self, county, date_ref):
        """
        Args:
            county: County model instance
            date_ref: datetime.date — the reference date (today for inference,
                      snapshot_date for historical training)

        Returns:
            dict with keys from AQ_FEATURE_COLS
        """
        from apps.air_quality.models import AirQualityObservation

        since = date_ref - timedelta(days=30)
        qs = AirQualityObservation.objects.filter(
            county=county,
            observed_at__date__gte=since,
            observed_at__date__lte=date_ref,
        )

        aqi_values = list(qs.values_list("aqi", flat=True))
        if not aqi_values:
            return self._zeros()

        pm25_count = qs.filter(pollutant="PM2.5").count()

        return {
            "aq_obs_count": len(aqi_values),
            "aq_max_aqi": max(aqi_values),
            "aq_mean_aqi": round(sum(aqi_values) / len(aqi_values), 2),
            "aq_unhealthy_days": sum(1 for v in aqi_values if v > 100),
            "aq_pm25_fraction": round(pm25_count / len(aqi_values), 4),
        }

    @staticmethod
    def _zeros():
        return {col: 0 for col in AQ_FEATURE_COLS}
