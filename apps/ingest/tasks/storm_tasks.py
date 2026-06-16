import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import transaction
from django.utils import timezone

from celery import shared_task

from apps.geodata.models import State
from apps.ingest.clients.noaa_client import NOAAClient
from apps.storms.models import ActiveAlert, StormEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# NWS GeoJSON polygon coordinates come as [lng, lat] lists; this converts them.
def _parse_geometry(geometry):
    """Convert a NWS GeoJSON geometry dict into a Django GEOSGeometry object.

    NWS alert geometries are either Polygon or MultiPolygon.  We always
    store as MultiPolygon for consistency with the model field.
    """
    if not geometry:
        return None
    geo_type = geometry.get("type", "")
    coords = geometry.get("coordinates")
    if not coords:
        return None
    try:
        if geo_type == "Polygon":
            return MultiPolygon(Polygon(*coords))
        elif geo_type == "MultiPolygon":
            return MultiPolygon(*[Polygon(*ring) for ring in coords])
    except Exception as exc:
        logger.warning(f"Could not parse alert geometry: {exc}")
    return None


def _parse_damage(value_str):
    """Parse NOAA Storm Events damage strings like '10K', '2.5M' into USD Decimal."""
    if not value_str or value_str.strip() in ("", "0"):
        return Decimal("0")
    value_str = value_str.strip().upper()
    multipliers = {"K": Decimal("1000"), "M": Decimal("1000000"), "B": Decimal("1000000000")}
    try:
        if value_str[-1] in multipliers:
            return (Decimal(value_str[:-1]) * multipliers[value_str[-1]]).quantize(Decimal("0.01"))
        return Decimal(value_str).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0")


def _parse_dt(date_str, time_str="0000", tz_str="UTC-0"):
    """Parse NOAA Storm Events BEGIN/END date + time columns into an aware datetime."""
    if not date_str:
        return None
    try:
        dt_str = f"{date_str} {time_str.zfill(4)}"
        naive = datetime.strptime(dt_str, "%d-%b-%y %H%M")
        return timezone.make_aware(naive, timezone.utc)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Task 1 – NWS Active Alerts
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3)
def ingest_active_alerts(self):
    """
    Celery task to ingest active severe weather alerts from NWS.
    Runs every 15 minutes.

    Fetches the GeoJSON-LD payload from api.weather.gov/alerts/active,
    upserts each feature into ActiveAlert, and returns the count of
    records written.
    """
    client = NOAAClient()
    logger.info("Fetching active weather alerts from NWS.")

    try:
        data = client.get_active_alerts()
    except Exception as exc:
        logger.error(f"NWS API request failed: {exc}")
        raise self.retry(exc=exc, countdown=60)

    if not data or "features" not in data:
        logger.warning("No features returned from NWS API.")
        return 0

    features = data["features"]
    logger.info(f"Received {len(features)} alert features from NWS.")

    success_count = 0

    for feature in features:
        props = feature.get("properties", {})
        alert_id = props.get("id") or feature.get("id")
        if not alert_id:
            logger.warning("Skipping alert feature with no id.")
            continue

        # Minor alerts are not actionable; skip at ingest to keep the DB clean.
        if (props.get("severity") or "").strip().lower() == "minor":
            continue

        try:
            geometry = _parse_geometry(feature.get("geometry"))
            affected_zones = props.get("affectedZones") or []

            # Temporal fields
            effective_raw = props.get("effective") or props.get("sent")
            expires_raw = props.get("expires") or props.get("ends")
            try:
                effective = (
                    datetime.fromisoformat(effective_raw.replace("Z", "+00:00"))
                    if effective_raw
                    else timezone.now()
                )
                expires = (
                    datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
                    if expires_raw
                    else timezone.now()
                )
            except (ValueError, AttributeError):
                effective = timezone.now()
                expires = timezone.now()

            defaults = {
                "event_type": props.get("event", "Unknown"),
                "severity": props.get("severity", "Unknown"),
                "urgency": props.get("urgency", "Unknown"),
                "certainty": props.get("certainty", "Unknown"),
                "headline": props.get("headline") or props.get("event", ""),
                "description": props.get("description") or "",
                "instruction": props.get("instruction") or "",
                "effective": effective,
                "expires": expires,
                "affected_zones": affected_zones,
                "geometry": geometry,
            }

            with transaction.atomic():
                ActiveAlert.objects.update_or_create(alert_id=alert_id, defaults=defaults)
            success_count += 1

        except Exception as exc:
            logger.error(f"Failed to upsert alert {alert_id}: {exc}")
            continue

    logger.info(f"Successfully processed {success_count}/{len(features)} alerts.")
    return success_count


# ---------------------------------------------------------------------------
# Task 2 – NOAA Storm Events DB (CDO CSV)
# ---------------------------------------------------------------------------

# NOAA CDO dataset ID for Storm Events Details
_CDO_STORM_EVENTS_DATASET = "STORM_EVENTS"

# Column mapping: CSV header → StormEvent field
_COLUMN_MAP = {
    "EVENT_ID": "event_id",
    "EVENT_TYPE": "event_type",
    "BEGIN_DATE_TIME": None,  # handled explicitly
    "END_DATE_TIME": None,  # handled explicitly
    "BEGIN_DATE": None,  # fallback date column
    "BEGIN_TIME": None,  # fallback time column
    "END_DATE": None,
    "END_TIME": None,
    "CZ_TIMEZONE": None,  # used for timezone offset
    "STATE": None,  # used for FK lookup
    "MAGNITUDE": "magnitude",
    "MAGNITUDE_TYPE": "magnitude_type",
    "DEATHS_DIRECT": "deaths_direct",
    "INJURIES_DIRECT": "injuries_direct",
    "DAMAGE_PROPERTY": None,  # parsed via helper
    "DAMAGE_CROPS": None,  # parsed via helper
    "EPISODE_NARRATIVE": "episode_narrative",
    "EVENT_NARRATIVE": "event_narrative",
    "BEGIN_LAT": None,  # used for PointField
    "BEGIN_LON": None,
    "END_LAT": None,
    "END_LON": None,
}


def _build_point(lat_str, lon_str):
    """Build a Point geometry from raw lat/lon strings. Returns None on failure."""
    try:
        lat = float(lat_str)
        lon = float(lon_str)
        return Point(lon, lat, srid=4326)
    except (TypeError, ValueError):
        return None


def _parse_storm_row(row, state_cache):
    """
    Parse a single CSV row dict into a dict of StormEvent field values.

    Args:
        row: dict from csv.DictReader
        state_cache: dict mapping uppercase state name → State instance

    Returns:
        dict suitable for StormEvent.objects.update_or_create, or None to skip.
    """
    event_id = row.get("EVENT_ID", "").strip()
    if not event_id:
        return None

    # State FK lookup
    state_name = (row.get("STATE") or row.get("STATE_ABBR") or "").strip().upper()
    state = state_cache.get(state_name)
    if not state:
        # Try by abbreviation
        state = State.objects.filter(abbreviation__iexact=state_name).first()
        if not state:
            logger.debug(f"Skipping storm event {event_id}: unknown state '{state_name}'")
            return None
        state_cache[state_name] = state

    # Date/time parsing — CDO delivers "BEGIN_DATE_TIME" in combined form or separate cols
    begin_dt = _parse_dt(row.get("BEGIN_DATE"), row.get("BEGIN_TIME"), row.get("CZ_TIMEZONE"))
    end_dt = _parse_dt(row.get("END_DATE"), row.get("END_TIME"), row.get("CZ_TIMEZONE"))
    if begin_dt is None:
        logger.debug(f"Skipping storm event {event_id}: could not parse begin date.")
        return None

    # Geometry
    begin_loc = _build_point(row.get("BEGIN_LAT"), row.get("BEGIN_LON"))
    end_loc = _build_point(row.get("END_LAT"), row.get("END_LON"))

    # Numeric / damage fields
    try:
        magnitude = Decimal(row.get("MAGNITUDE") or 0)
    except InvalidOperation:
        magnitude = None

    return {
        "event_id": event_id,
        "state": state,
        "event_type": row.get("EVENT_TYPE", "").strip(),
        "begin_date": begin_dt,
        "end_date": end_dt,
        "begin_location": begin_loc,
        "end_location": end_loc,
        "magnitude": magnitude,
        "magnitude_type": (row.get("MAGNITUDE_TYPE") or "").strip() or None,
        "deaths_direct": int(row.get("DEATHS_DIRECT") or 0),
        "injuries_direct": int(row.get("INJURIES_DIRECT") or 0),
        "damage_property_usd": _parse_damage(row.get("DAMAGE_PROPERTY")),
        "damage_crops_usd": _parse_damage(row.get("DAMAGE_CROPS")),
        "episode_narrative": (row.get("EPISODE_NARRATIVE") or "").strip() or None,
        "event_narrative": (row.get("EVENT_NARRATIVE") or "").strip() or None,
    }


@shared_task(bind=True, max_retries=3)
def ingest_storm_events(self, year=None):
    """
    Download and parse NOAA Storm Events DB CSV via the CDO API and
    upsert records into StormEvent.

    Args:
        year (int, optional): The year to ingest. Defaults to the previous
            calendar year so the data is complete.

    The CDO endpoint for Storm Events returns CSV data. Each row is parsed
    and upserted keyed on the unique EVENT_ID column.
    """
    client = NOAAClient()

    if year is None:
        year = datetime.now().year - 1

    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    logger.info(f"Starting NOAA Storm Events ingestion for year={year}.")

    if not client.cdo_token:
        logger.warning(
            "NOAA_CDO_TOKEN is not set — Storm Events ingestion requires a CDO token. "
            "Obtain one at https://www.ncdc.noaa.gov/cdo-web/token and set NOAA_CDO_TOKEN."
        )
        return 0

    # Fetch CSV from CDO
    try:
        csv_text = client.get_storm_events_csv(start_date=start_date, end_date=end_date)
    except Exception as exc:
        logger.error(f"Failed to fetch Storm Events CSV from CDO: {exc}")
        raise self.retry(exc=exc, countdown=120)

    if not csv_text:
        logger.warning("CDO returned empty Storm Events CSV.")
        return 0

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    logger.info(f"Parsing {len(rows)} storm event rows for year={year}.")

    # Pre-warm state cache to avoid N+1 queries
    state_cache = {s.name.upper(): s for s in State.objects.all()}

    success_count = 0
    skip_count = 0

    for row in rows:
        parsed = _parse_storm_row(row, state_cache)
        if parsed is None:
            skip_count += 1
            continue

        event_id = parsed.pop("event_id")
        state = parsed.pop("state")
        begin_date = parsed.pop("begin_date")

        try:
            with transaction.atomic():
                StormEvent.objects.update_or_create(
                    event_id=event_id,
                    defaults={
                        "state": state,
                        "begin_date": begin_date,
                        **parsed,
                    },
                )
            success_count += 1
        except Exception as exc:
            logger.error(f"Failed to upsert StormEvent {event_id}: {exc}")

    logger.info(
        f"Storm Events ingestion complete: {success_count} upserted, "
        f"{skip_count} skipped, {len(rows)} total rows for year={year}."
    )
    return success_count
