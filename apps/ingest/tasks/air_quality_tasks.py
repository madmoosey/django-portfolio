import logging
from datetime import datetime, timezone

from django.db import transaction

from celery import shared_task

from apps.air_quality.models import AirQualityObservation
from apps.geodata.models import County, State
from apps.ingest.clients.airnow_client import AirNowClient, aqi_category

logger = logging.getLogger(__name__)

# Only store readings at or above this AQI (skip "Good" — not actionable)
_MIN_AQI = 51


def _parse_observed_at(date_str, hour_int):
    """
    Combine AirNow 'DateObserved' ('YYYY-MM-DD') and 'HourObserved' (0-23 UTC)
    into a timezone-aware datetime.
    """
    try:
        naive = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(
            hour=int(hour_int), minute=0, second=0, microsecond=0
        )
        return naive.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError) as exc:
        logger.warning(f"Could not parse AirNow datetime '{date_str}' h={hour_int}: {exc}")
        return None


@shared_task(bind=True, max_retries=3)
def ingest_air_quality_observations(self):
    """
    Hourly Celery task: fetch current primary AQI readings for all US
    reporting areas from the EPA AirNow API and upsert
    AirQualityObservation records.

    Strategy:
      - Fetches one record per (reporting_area, pollutant) from AirNow.
      - Skips AQI < 51 ("Good") to keep the table focused on bad air.
      - Selects the highest-AQI pollutant as the *primary* record when an
        area reports multiple pollutants above the threshold.
      - Resolves State via state abbreviation code.
      - Resolves County via a PostGIS ST_Contains point-in-polygon query
        (lat/lon from AirNow) — falls back to NULL for offshore / boundary
        monitoring stations.
      - Upserts keyed on (reporting_area, observed_at, pollutant).

    Returns:
        dict: {'upserted': N, 'skipped': N, 'total_fetched': N}

    Scheduled hourly at :15 (see config/celery.py).
    """
    logger.info("Starting AirNow air quality ingestion.")

    client = AirNowClient()

    if not client.api_key:
        logger.warning("AIRNOW_API_KEY not set — skipping AQ ingestion.")
        return {"upserted": 0, "skipped": 0, "total_fetched": 0}

    try:
        raw_obs = client.get_current_observations()
    except Exception as exc:
        logger.error(f"AirNow fetch failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)

    if not raw_obs:
        logger.warning("AirNow returned no observations.")
        return {"upserted": 0, "skipped": 0, "total_fetched": 0}

    logger.info(f"Received {len(raw_obs)} raw observations from AirNow.")

    # Pre-warm lookup caches
    state_cache = {s.abbreviation.upper(): s for s in State.objects.all()}

    upserted = 0
    skipped = 0

    for obs in raw_obs:
        aqi_val = obs.get("AQI", -1)

        # AirNow returns -1 for unavailable readings
        if not isinstance(aqi_val, int) or aqi_val < _MIN_AQI:
            skipped += 1
            continue

        reporting_area = (obs.get("ReportingArea") or "").strip()
        state_code = (obs.get("StateCode") or "").strip().upper()
        pollutant = (obs.get("ParameterName") or "").strip()

        if not reporting_area or not pollutant:
            skipped += 1
            continue

        observed_at = _parse_observed_at(
            obs.get("DateObserved", ""),
            obs.get("HourObserved", 0),
        )
        if observed_at is None:
            skipped += 1
            continue

        # Category label — prefer AirNow's own label, fall back to computed
        category_info = obs.get("Category") or {}
        category_name = (category_info.get("Name") or aqi_category(aqi_val)).strip()

        # Coordinates
        lat = obs.get("Latitude")
        lon = obs.get("Longitude")
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except (ValueError, TypeError):
            lat = lon = None

        # Resolve State FK
        state = state_cache.get(state_code)
        if not state and state_code:
            state = State.objects.filter(abbreviation__iexact=state_code).first()
            if state:
                state_cache[state_code] = state

        # Resolve County FK via PostGIS ST_Contains (point-in-polygon).
        # Lat/lon may be None if the endpoint doesn't return coordinates.
        county = None
        point = None
        if lat is not None and lon is not None:
            from django.contrib.gis.geos import Point

            point = Point(lon, lat, srid=4326)
            county = County.objects.filter(geometry__contains=point).select_related("state").first()

        try:
            with transaction.atomic():
                AirQualityObservation.objects.update_or_create(
                    reporting_area=reporting_area,
                    observed_at=observed_at,
                    pollutant=pollutant,
                    defaults={
                        "state": state,
                        "county": county,
                        "latitude": lat,
                        "longitude": lon,
                        # Keep PostGIS PointField in sync with lat/lon so the
                        # AQ layer supports ST_DWithin / bbox spatial queries.
                        "location": point if (lat is not None and lon is not None) else None,
                        "aqi": aqi_val,
                        "aqi_category": category_name,
                    },
                )
            upserted += 1
        except Exception as exc:
            logger.error(
                f"Failed to upsert AQ obs for {reporting_area} "
                f"({pollutant} AQI={aqi_val}): {exc}",
                exc_info=True,
            )

    logger.info(
        f"AQ ingestion complete: {upserted} upserted, {skipped} skipped, "
        f"{len(raw_obs)} total fetched."
    )
    return {"upserted": upserted, "skipped": skipped, "total_fetched": len(raw_obs)}
