"""Hurricane risk feature extractor."""

import logging

from .storm_helpers import active_alert_stats, storm_event_stats

logger = logging.getLogger(__name__)

HURRICANE_FEATURE_COLS = [
    "hur_historical_count",
    "hur_recent_count",
    "hur_deaths",
    "hur_alert_count",
    "hur_extreme_alert_count",
    "hur_days_since_last_alert",
    "hur_coastal_proximity",  # 1 if county centroid latitude < 35 and near coast
]

_KEYWORDS = ["hurricane", "tropical storm", "tropical depression", "typhoon"]


class HurricaneFeatureExtractor:
    """Extract hurricane risk features for a county."""

    def extract(self, county, date_ref):
        ev = storm_event_stats(county, date_ref, _KEYWORDS, lookback_days=365 * 10)
        al = active_alert_stats(county, date_ref, _KEYWORDS)

        # Simple coastal proximity heuristic: latitude south of 35° and
        # longitude in Atlantic/Gulf corridor (-100 to -60)
        coastal = 0
        if county.geometry:
            try:
                centroid = county.geometry.centroid
                if centroid.y < 35 and -100 < centroid.x < -60:
                    coastal = 1
            except Exception:
                pass

        return {
            "hur_historical_count": ev["count"],
            "hur_recent_count": ev["recent_count"],
            "hur_deaths": min(ev["deaths"], 500),
            "hur_alert_count": al["alert_count"],
            "hur_extreme_alert_count": al["extreme_alert_count"],
            "hur_days_since_last_alert": al["days_since_last_alert"],
            "hur_coastal_proximity": coastal,
        }
