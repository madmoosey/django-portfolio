"""Tornado risk feature extractor."""

import logging

from .storm_helpers import active_alert_stats, storm_event_stats

logger = logging.getLogger(__name__)

TORNADO_FEATURE_COLS = [
    "tor_historical_count",
    "tor_recent_count",
    "tor_deaths",
    "tor_max_ef_score",  # maximum EF rating observed (magnitude field)
    "tor_alert_count",
    "tor_extreme_alert_count",
    "tor_days_since_last_alert",
    "tor_alley_proximity",  # 1 if in classic tornado alley lon band
]

_KEYWORDS = ["tornado", "funnel cloud"]


class TornadoFeatureExtractor:
    """Extract tornado risk features for a county."""

    def extract(self, county, date_ref):
        ev = storm_event_stats(county, date_ref, _KEYWORDS, lookback_days=365 * 10)
        al = active_alert_stats(county, date_ref, _KEYWORDS)

        # Max EF rating from historical events (magnitude = EF scale 0-5)
        max_ef = 0
        if ev["has_any"]:
            from datetime import timedelta

            from django.db.models import Max, Q

            from apps.storms.models import StormEvent

            since = date_ref - timedelta(days=365 * 10)
            q = Q()
            for kw in _KEYWORDS:
                q |= Q(event_type__icontains=kw)
            agg = (
                StormEvent.objects.filter(
                    county=county,
                    begin_date__date__gte=since,
                )
                .filter(q)
                .aggregate(max_mag=Max("magnitude"))
            )
            max_ef = min(float(agg["max_mag"] or 0), 5.0)

        # Tornado alley: central US, roughly lon -103 to -75, lat 25-50
        alley = 0
        if county.geometry:
            try:
                c = county.geometry.centroid
                if -103 < c.x < -75 and 25 < c.y < 50:
                    alley = 1
            except Exception:
                pass

        return {
            "tor_historical_count": ev["count"],
            "tor_recent_count": ev["recent_count"],
            "tor_deaths": min(ev["deaths"], 200),
            "tor_max_ef_score": max_ef,
            "tor_alert_count": al["alert_count"],
            "tor_extreme_alert_count": al["extreme_alert_count"],
            "tor_days_since_last_alert": al["days_since_last_alert"],
            "tor_alley_proximity": alley,
        }
