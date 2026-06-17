"""
Severe weather feature extractor for the ML risk pipeline.

Uses PostGIS ST_Intersects to find ActiveAlert records whose polygon
overlaps the county geometry, then aggregates 90-day statistics.
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

SW_FEATURE_COLS = [
    "sw_alert_count",
    "sw_extreme_count",
    "sw_days_since_last",
    "sw_has_tornado",
    "sw_has_flood",
    "sw_has_thunderstorm",
]


class SevereWeatherFeatureExtractor:
    """Extract 90-day NWS severe weather statistics per county."""

    def extract(self, county, date_ref):
        """
        Args:
            county: County model instance (must have geometry != NULL)
            date_ref: datetime.date

        Returns:
            dict with keys from SW_FEATURE_COLS
        """
        from apps.storms.models import ActiveAlert

        if county.geometry is None:
            logger.debug(f"County {county.fips_code} has no geometry — returning zero features.")
            return self._zeros()

        since = date_ref - timedelta(days=90)

        qs = ActiveAlert.objects.filter(
            geometry__intersects=county.geometry,
            effective__date__gte=since,
            effective__date__lte=date_ref,
        )

        count = qs.count()
        if count == 0:
            return self._zeros()

        extreme = qs.filter(severity__in=["Extreme", "Severe"]).count()
        last_effective = qs.order_by("-effective").values_list("effective", flat=True).first()
        days_since = (date_ref - last_effective.date()).days if last_effective else 90

        event_types = [e.lower() for e in qs.values_list("event_type", flat=True) if e]

        return {
            "sw_alert_count": min(count, 100),  # cap outliers
            "sw_extreme_count": min(extreme, 50),
            "sw_days_since_last": min(days_since, 90),
            "sw_has_tornado": int(any("tornado" in e for e in event_types)),
            "sw_has_flood": int(any("flood" in e for e in event_types)),
            "sw_has_thunderstorm": int(any("thunderstorm" in e for e in event_types)),
        }

    @staticmethod
    def _zeros():
        return {col: 0 for col in SW_FEATURE_COLS}
