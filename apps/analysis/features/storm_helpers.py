"""
Shared utilities for StormEvent-based feature extractors.

StormEvent (NOAA historical) and ActiveAlert (NWS real-time) are both
used across the event-type predictors. This module provides helpers that
are reused by hurricane, tornado, heat-wave, and wildfire extractors.
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def storm_event_stats(county, date_ref, event_keywords, lookback_days=365 * 5):
    """
    Aggregate historical StormEvent records for a county filtered by
    event_type keywords.

    Returns a dict with:
        count, recent_count (last 90d), deaths, damage_usd, has_any
    """
    from apps.storms.models import StormEvent

    since = date_ref - timedelta(days=lookback_days)
    since_90d = date_ref - timedelta(days=90)

    qs = StormEvent.objects.filter(
        county=county,
        begin_date__date__gte=since,
        begin_date__date__lte=date_ref,
    )
    # Keyword match across all supplied terms
    from django.db.models import Q

    q = Q()
    for kw in event_keywords:
        q |= Q(event_type__icontains=kw)
    qs = qs.filter(q)

    count = qs.count()
    if count == 0:
        return {"count": 0, "recent_count": 0, "deaths": 0, "damage_usd": 0.0, "has_any": 0}

    recent_count = qs.filter(begin_date__date__gte=since_90d).count()
    agg = qs.aggregate(
        total_deaths=__import__("django.db.models", fromlist=["Sum"]).Sum("deaths_direct"),
        total_damage=__import__("django.db.models", fromlist=["Sum"]).Sum("damage_property_usd"),
    )
    return {
        "count": min(count, 200),
        "recent_count": min(recent_count, 50),
        "deaths": int(agg["total_deaths"] or 0),
        "damage_usd": float(agg["total_damage"] or 0.0),
        "has_any": 1,
    }


def active_alert_stats(county, date_ref, event_keywords, lookback_days=90):
    """
    Aggregate ActiveAlert records whose geometry intersects the county and
    event_type matches any of the keywords.
    """
    from apps.storms.models import ActiveAlert

    if county.geometry is None:
        return {"alert_count": 0, "extreme_alert_count": 0, "days_since_last_alert": 90}

    since = date_ref - timedelta(days=lookback_days)
    from django.db.models import Q

    q = Q()
    for kw in event_keywords:
        q |= Q(event_type__icontains=kw)

    qs = ActiveAlert.objects.filter(
        geometry__intersects=county.geometry,
        effective__date__gte=since,
        effective__date__lte=date_ref,
    ).filter(q)

    count = qs.count()
    if count == 0:
        return {"alert_count": 0, "extreme_alert_count": 0, "days_since_last_alert": lookback_days}

    extreme = qs.filter(severity__in=["Extreme", "Severe"]).count()
    last = qs.order_by("-effective").values_list("effective", flat=True).first()
    days_since = (date_ref - last.date()).days if last else lookback_days

    return {
        "alert_count": min(count, 50),
        "extreme_alert_count": min(extreme, 20),
        "days_since_last_alert": min(days_since, lookback_days),
    }
