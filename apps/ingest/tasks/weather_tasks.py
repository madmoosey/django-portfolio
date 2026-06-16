import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.gis.geos import Point
from django.db import transaction
from django.utils import timezone

from celery import shared_task

from apps.geodata.models import County
from apps.ingest.clients.noaa_client import NOAAClient
from apps.weather.models import TemperatureObservation, WeatherStation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_decimal(value, decimal_places=1):
    """
    Coerce a raw CDO value (float, int, or string) to a Decimal rounded to
    *decimal_places*, or return None if the value is absent/unparseable.
    """
    if value is None:
        return None
    try:
        return round(Decimal(str(value)), decimal_places)
    except InvalidOperation:
        return None


def _parse_date(date_str):
    """
    Parse a CDO date string (e.g. '2024-06-15' or '2024-06-15T00:00:00')
    into a Python date object.  Returns None on failure.
    """
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str[: len(fmt)], fmt).date()
        except ValueError:
            continue
    logger.warning(f"Could not parse date string: {date_str!r}")
    return None


# ---------------------------------------------------------------------------
# Task 1 – Station seed / sync
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3)
def sync_weather_stations(self):
    """
    Seed and keep the WeatherStation table current by syncing metadata from
    the NOAA CDO /stations endpoint (GHCND dataset, US only).

    This task should be run once manually to populate the table, and then
    periodically (e.g. monthly) to pick up newly commissioned stations or
    decommission old ones.

    Strategy:
      - New stations   → created with is_active=True.
      - Existing stations whose CDO maxdate is more than 400 days in the past
        → marked is_active=False (station is no longer reporting).
      - All other existing stations → name/location/elevation refreshed.

    Returns:
        dict: {'created': N, 'updated': N, 'deactivated': N, 'total_fetched': N}

    Requires NOAA_CDO_TOKEN.  Without it, the task exits immediately with a
    warning and returns zeroed counts.
    """
    logger.info("Starting weather station sync from NOAA CDO.")

    client = NOAAClient()

    if not client.cdo_token:
        logger.warning(
            "NOAA_CDO_TOKEN is not set — station sync requires a CDO token. "
            "Obtain one at https://www.ncdc.noaa.gov/cdo-web/token and set NOAA_CDO_TOKEN."
        )
        return {"created": 0, "updated": 0, "deactivated": 0, "total_fetched": 0}

    try:
        stations_data = client.get_stations()
    except Exception as exc:
        logger.error(f"Failed to fetch station list from CDO: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)

    if not stations_data:
        logger.warning("CDO returned no stations — nothing to sync.")
        return {"created": 0, "updated": 0, "deactivated": 0, "total_fetched": 0}

    # Threshold: stations with no data in the last ~13 months are inactive.
    stale_cutoff = (timezone.now() - timedelta(days=400)).date()

    created = 0
    updated = 0
    deactivated = 0

    for raw in stations_data:
        station_id = raw.get("id", "").strip()
        if not station_id:
            continue

        lat = raw.get("latitude")
        lon = raw.get("longitude")
        if lat is None or lon is None:
            logger.debug(f"Skipping station {station_id}: missing coordinates.")
            continue

        name = (raw.get("name") or station_id).strip()
        elevation = raw.get("elevation")  # metres, may be None

        # Determine is_active from the station's most recent data date
        maxdate_str = raw.get("maxdate")
        maxdate = _parse_date(maxdate_str)
        is_active = (maxdate is None) or (maxdate >= stale_cutoff)

        location = Point(float(lon), float(lat), srid=4326)
        elevation_m = _to_decimal(elevation, decimal_places=2) if elevation is not None else None

        try:
            obj, was_created = WeatherStation.objects.get_or_create(
                station_id=station_id,
                defaults={
                    "name": name,
                    "location": location,
                    "elevation_m": elevation_m,
                    "is_active": is_active,
                },
            )

            if was_created:
                created += 1
                logger.debug(f"Created station {station_id} ({name}).")
            else:
                # Refresh mutable fields; preserve any manual overrides to is_active
                # only when the station has gone stale.
                changed_fields = []

                if obj.name != name:
                    obj.name = name
                    changed_fields.append("name")

                if obj.location.x != location.x or obj.location.y != location.y:
                    obj.location = location
                    changed_fields.append("location")

                if obj.elevation_m != elevation_m:
                    obj.elevation_m = elevation_m
                    changed_fields.append("elevation_m")

                if not is_active and obj.is_active:
                    obj.is_active = False
                    changed_fields.append("is_active")
                    deactivated += 1
                    logger.debug(
                        f"Deactivated stale station {station_id} " f"(last data: {maxdate_str})."
                    )

                if changed_fields:
                    changed_fields.append("updated_at")
                    obj.save(update_fields=changed_fields)
                    if "is_active" not in changed_fields:
                        updated += 1

        except Exception as exc:
            logger.error(f"Failed to upsert station {station_id}: {exc}", exc_info=True)
            continue

    logger.info(
        f"Station sync complete: {created} created, {updated} updated, "
        f"{deactivated} deactivated, {len(stations_data)} total fetched from CDO."
    )
    return {
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
        "total_fetched": len(stations_data),
    }


@shared_task(bind=True, max_retries=3)
def ingest_temperature_observations(self):
    """
    Celery task to ingest yesterday's temperature and precipitation data for
    all active WeatherStations using the NOAA CDO daily-summaries endpoint.

    For each active station the task:
      1. Calls NOAAClient.get_daily_summaries() for yesterday's date.
      2. Parses TMAX, TMIN, PRCP from the response payload.
      3. Derives TAVG as (TMAX + TMIN) / 2 when both are present.
      4. Upserts a TemperatureObservation row keyed on (station, date).

    Returns:
        int: Number of stations successfully ingested.
    """
    client = NOAAClient()
    stations = WeatherStation.objects.filter(is_active=True).select_related("county")

    yesterday = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    station_count = stations.count()
    logger.info(f"Starting temperature ingestion for {station_count} stations on {yesterday}.")

    if station_count == 0:
        logger.warning("No active weather stations found — nothing to ingest.")
        return 0

    success_count = 0
    error_count = 0

    for station in stations:
        try:
            records = client.get_daily_summaries(station.station_id, yesterday, yesterday)

            if not records:
                logger.debug(f"No data returned for station {station.station_id} on {yesterday}.")
                continue

            with transaction.atomic():
                for record in records:
                    obs_date = _parse_date(record.get("DATE") or yesterday)
                    if obs_date is None:
                        logger.warning(
                            f"Skipping record with unparseable date for station "
                            f"{station.station_id}: {record!r}"
                        )
                        continue

                    tmax = _to_decimal(record.get("TMAX"))
                    tmin = _to_decimal(record.get("TMIN"))
                    prcp = _to_decimal(record.get("PRCP"))

                    # Derive TAVG when both extremes are available
                    tavg = None
                    if tmax is not None and tmin is not None:
                        tavg = round((tmax + tmin) / Decimal("2"), 1)

                    TemperatureObservation.objects.update_or_create(
                        station=station,
                        date=obs_date,
                        defaults={
                            "tmax_celsius": tmax,
                            "tmin_celsius": tmin,
                            "tavg_celsius": tavg,
                            "precipitation_mm": prcp,
                        },
                    )

            success_count += 1

        except Exception as exc:
            error_count += 1
            logger.error(
                f"Failed to ingest data for station {station.station_id}: {exc}",
                exc_info=True,
            )
            # Per-station failures are logged and skipped; we do not retry the
            # entire task for a single bad station.
            continue

    logger.info(
        f"Temperature ingestion complete: {success_count}/{station_count} stations "
        f"ingested, {error_count} errors on {yesterday}."
    )

    # Retry the whole task only if *every* station failed (likely a network issue).
    if error_count > 0 and success_count == 0:
        raise self.retry(countdown=120)

    return success_count


# ---------------------------------------------------------------------------
# Task 2 – Spatial station → county join
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=2)
def sync_station_counties(self):
    """
    Spatially map each WeatherStation to the County whose geometry contains
    the station's point, using a PostGIS ST_Contains query.

    Runs as a maintenance task (e.g. nightly) to keep the station.county FK
    current whenever new stations are added or station locations are corrected.

    Returns:
        dict: {'updated': N, 'cleared': N, 'total': N}
    """
    logger.info("Starting spatial station → county sync.")

    stations = WeatherStation.objects.all().select_related("county")
    total = stations.count()

    if total == 0:
        logger.warning("No weather stations found — nothing to sync.")
        return {"updated": 0, "cleared": 0, "total": 0}

    updated = 0
    cleared = 0

    try:
        with transaction.atomic():
            for station in stations:
                # PostGIS ST_Contains: find the county whose boundary contains
                # the station's point geometry.
                containing_county = (
                    County.objects.filter(geometry__contains=station.location)
                    .select_related("state")
                    .first()
                )

                if containing_county and station.county_id != containing_county.pk:
                    old = station.county.name if station.county else "None"
                    station.county = containing_county
                    station.save(update_fields=["county", "updated_at"])
                    logger.debug(
                        f"Station {station.station_id}: county {old!r} → "
                        f"{containing_county.name!r} ({containing_county.fips_code})"
                    )
                    updated += 1

                elif containing_county is None and station.county is not None:
                    # Station location falls outside all known county boundaries
                    # (e.g. offshore buoy). Clear the stale FK.
                    logger.debug(
                        f"Station {station.station_id}: no containing county found, "
                        f"clearing stale FK ({station.county.name!r})."
                    )
                    station.county = None
                    station.save(update_fields=["county", "updated_at"])
                    cleared += 1

    except Exception as exc:
        logger.error(f"Spatial county sync failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)

    logger.info(
        f"Station → county sync complete: {updated} updated, {cleared} cleared, "
        f"{total} total stations."
    )
    return {"updated": updated, "cleared": cleared, "total": total}
