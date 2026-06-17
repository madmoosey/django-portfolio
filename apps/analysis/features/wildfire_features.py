"""Wildfire risk feature extractor.

Wildfire data comes from two sources:
  1. NOAA StormEvent records with wildfire event types
  2. AirQualityObservation PM2.5 spikes — wildfires are the dominant driver of
     extreme PM2.5 episodes, especially in Western counties.  A sustained
     PM2.5-driven AQI above 150 is a strong wildfire smoke proxy.
"""

import logging
from datetime import timedelta

from .storm_helpers import active_alert_stats, storm_event_stats

logger = logging.getLogger(__name__)

WILDFIRE_FEATURE_COLS = [
    "wf_historical_count",
    "wf_recent_count",
    "wf_alert_count",
    "wf_extreme_alert_count",
    "wf_days_since_last_alert",
    "wf_pm25_max_aqi",  # peak PM2.5-driven AQI in last 30 days
    "wf_pm25_smoke_days",  # days AQI > 150 from PM2.5 (smoke events)
    "wf_western_proximity",  # 1 if county is west of -100° (wildfire corridor)
    "wf_season_factor",  # 1 if month is May-Oct (fire season)
]

_KEYWORDS = ["wildfire", "wild fire", "red flag", "fire weather"]


class WildfireFeatureExtractor:
    """Extract wildfire risk features for a county."""

    def extract(self, county, date_ref):
        ev = storm_event_stats(county, date_ref, _KEYWORDS, lookback_days=365 * 10)
        al = active_alert_stats(county, date_ref, _KEYWORDS)

        # PM2.5 smoke proxy — last 30 days
        pm25_max_aqi = 0
        pm25_smoke_days = 0
        try:
            from apps.air_quality.models import AirQualityObservation

            since = date_ref - timedelta(days=30)
            pm25_qs = AirQualityObservation.objects.filter(
                county=county,
                pollutant="PM2.5",
                observed_at__date__gte=since,
                observed_at__date__lte=date_ref,
            )
            aqis = list(pm25_qs.values_list("aqi", flat=True))
            if aqis:
                pm25_max_aqi = max(aqis)
                pm25_smoke_days = sum(1 for v in aqis if v > 150)
        except Exception as exc:
            logger.debug(f"PM2.5 lookup failed for {county.fips_code}: {exc}")

        # Western US wildfire corridor (west of -100° longitude)
        western = 0
        if county.geometry:
            try:
                c = county.geometry.centroid
                if c.x < -100:
                    western = 1
            except Exception:
                pass

        # Peak fire season (Northern Hemisphere: May – October)
        season_factor = 1 if date_ref.month in (5, 6, 7, 8, 9, 10) else 0

        return {
            "wf_historical_count": ev["count"],
            "wf_recent_count": ev["recent_count"],
            "wf_alert_count": al["alert_count"],
            "wf_extreme_alert_count": al["extreme_alert_count"],
            "wf_days_since_last_alert": al["days_since_last_alert"],
            "wf_pm25_max_aqi": min(pm25_max_aqi, 500),
            "wf_pm25_smoke_days": min(pm25_smoke_days, 30),
            "wf_western_proximity": western,
            "wf_season_factor": season_factor,
        }
