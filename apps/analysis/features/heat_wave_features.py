"""Heat wave risk feature extractor."""

import logging

from .storm_helpers import active_alert_stats, storm_event_stats

logger = logging.getLogger(__name__)

HEAT_WAVE_FEATURE_COLS = [
    "heat_historical_count",
    "heat_recent_count",
    "heat_deaths",
    "heat_alert_count",
    "heat_extreme_alert_count",
    "heat_days_since_last_alert",
    "heat_southern_proximity",  # 1 if latitude < 36 (Sun Belt)
    "heat_season_factor",  # 1 if current month is Jun-Sep
]

_KEYWORDS = ["heat", "excessive heat", "heat wave", "heat advisory", "hot"]


class HeatWaveFeatureExtractor:
    """Extract heat wave risk features for a county."""

    def extract(self, county, date_ref):
        ev = storm_event_stats(county, date_ref, _KEYWORDS, lookback_days=365 * 10)
        al = active_alert_stats(county, date_ref, _KEYWORDS)

        # Sun Belt heuristic — states south of roughly 36° latitude are much
        # more heat-prone (AZ, TX, FL, GA, SC, etc.)
        southern = 0
        if county.geometry:
            try:
                c = county.geometry.centroid
                if c.y < 36:
                    southern = 1
            except Exception:
                pass

        # Peak heat season (Northern Hemisphere summer)
        season_factor = 1 if date_ref.month in (6, 7, 8, 9) else 0

        return {
            "heat_historical_count": ev["count"],
            "heat_recent_count": ev["recent_count"],
            "heat_deaths": min(ev["deaths"], 300),
            "heat_alert_count": al["alert_count"],
            "heat_extreme_alert_count": al["extreme_alert_count"],
            "heat_days_since_last_alert": al["days_since_last_alert"],
            "heat_southern_proximity": southern,
            "heat_season_factor": season_factor,
        }
