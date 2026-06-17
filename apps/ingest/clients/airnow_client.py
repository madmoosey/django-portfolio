"""
AirNow client — hourly public reporting-area flat-file feed.

Source:
    https://s3-us-west-1.amazonaws.com/files.airnowtech.org/airnow/today/reportingarea.dat

No API key required.  The file is updated every hour and covers all US
reporting areas.  It is pipe-delimited (17 fields) and uses 2-digit years.

Field layout:
    0  IssueDate     MM/DD/YY
    1  ObsDate       MM/DD/YY
    2  ObsTime       HH:MM  (local)
    3  TZ            EDT / CDT / MDT / PDT / AKDT / HST …
    4  hoursOffset   0 = current obs; <0 = historical; >0 = forecast
    5  RecType       O = observation  F = forecast
    6  isPrimary     Y = primary pollutant for this area  N = secondary
    7  ReportingArea city/area name
    8  StateCode     2-char abbreviation
    9  Latitude      float
    10 Longitude     float
    11 ParameterName PM2.5 / PM10 / OZONE / CO / NO2 / SO2
    12 AQI           integer  (-1 = unavailable)
    13 AQICategory   Good / Moderate / Unhealthy for Sensitive Groups / …
    14 ActionDay     Yes / No
    15 Discussion    (often blank)
    16 Agency

get_current_observations() normalises each row to the same PascalCase dict
shape expected by apps.ingest.tasks.air_quality_tasks, so that task is
unchanged.
"""

import logging
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_FEED_URL = (
    "https://s3-us-west-1.amazonaws.com" "/files.airnowtech.org/airnow/today/reportingarea.dat"
)

# Mapping from AirNow abbreviated timezone name → UTC offset hours.
# AirNow only emits the standard/daylight variants for the major US zones.
_TZ_OFFSETS: dict[str, int] = {
    "EST": -5,
    "EDT": -4,
    "CST": -6,
    "CDT": -5,
    "MST": -7,
    "MDT": -6,
    "PST": -8,
    "PDT": -7,
    "AKST": -9,
    "AKDT": -8,
    "HST": -10,
    "HAST": -10,
    "AST": -4,
    "ChST": 10,  # Guam / Northern Mariana Islands
}

# AQI category name → EPA number (1–6)
_CATEGORY_NUMBERS: dict[str, int] = {
    "good": 1,
    "moderate": 2,
    "unhealthy for sensitive groups": 3,
    "unhealthy": 4,
    "very unhealthy": 5,
    "hazardous": 6,
}

# AQI categories by breakpoint for fallback computation
_AQI_CATEGORIES = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
    (500, "Hazardous"),
]


def aqi_category(aqi_value: int) -> str:
    """Return the EPA category label for a given AQI integer."""
    for threshold, label in _AQI_CATEGORIES:
        if aqi_value <= threshold:
            return label
    return "Hazardous"


def _local_to_utc(date_str: str, time_str: str, tz_abbr: str) -> datetime | None:
    """
    Convert a flat-file local datetime (MM/DD/YY HH:MM <TZ>) to UTC.

    Returns a timezone-aware datetime or None on any parse error.
    """
    try:
        # 2-digit year: strptime %y maps 00-68 → 2000-2068, 69-99 → 1969-1999
        naive = datetime.strptime(f"{date_str.strip()} {time_str.strip()}", "%m/%d/%y %H:%M")
    except ValueError:
        return None

    offset_hours = _TZ_OFFSETS.get(tz_abbr.strip(), 0)  # assume UTC if unknown
    utc_offset = timezone(timedelta(hours=offset_hours))
    local_aware = naive.replace(tzinfo=utc_offset)
    return local_aware.astimezone(timezone.utc)


class AirNowClient:
    """
    Fetches the hourly AirNow reporting-area flat-file and returns a
    normalised list of observation dicts.

    The flat-file contains one row per (reporting_area, pollutant).
    We keep only:
      - RecType == 'O'         (observations, not forecasts)
      - hoursOffset == '0'     (current hour, not historical/future)
      - isPrimary == 'Y'       (dominant pollutant per area)

    No API key is required; the file is publicly available on S3.
    """

    # Kept for backward-compat with the task's `if not client.api_key` guard
    api_key: str = "flat-file"

    def __init__(self):
        self._session = requests.Session()

    def get_current_observations(self) -> list[dict]:
        """
        Download the hourly flat-file and return normalised observation dicts.

        Each dict has the same keys the ingest task expects:
            ReportingArea, StateCode, Latitude, Longitude,
            DateObserved (YYYY-MM-DD), HourObserved (0-23 UTC),
            LocalTimeZone, ParameterName,
            AQI (int), Category {'Number': int, 'Name': str}

        Returns [] on any network or parse error.
        """
        logger.info("Fetching AirNow flat-file feed: %s", _FEED_URL)

        try:
            resp = self._session.get(_FEED_URL, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("AirNow flat-file download failed: %s", exc)
            raise

        raw_text = resp.content.decode("latin-1")  # file uses latin-1 encoding
        lines = raw_text.splitlines()
        logger.info("Flat-file: %d raw lines downloaded.", len(lines))

        observations: list[dict] = []

        for lineno, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            parts = line.split("|")
            if len(parts) < 14:
                logger.debug("Line %d skipped: only %d fields", lineno, len(parts))
                continue

            # ── Filter: current observations only ──────────────────────────
            rec_type = parts[5].strip()  # 'O' or 'F'
            hours_offset = parts[4].strip()  # '0' = current hour
            is_primary = parts[6].strip()  # 'Y' = primary pollutant

            if rec_type != "O" or hours_offset != "0" or is_primary != "Y":
                continue

            # ── Parse AQI ──────────────────────────────────────────────────
            try:
                aqi_val = int(parts[12].strip())
            except (ValueError, IndexError):
                continue

            if aqi_val < 0:
                continue  # -1 = sensor unavailable

            # ── Parse coords ───────────────────────────────────────────────
            try:
                lat = float(parts[9].strip())
                lon = float(parts[10].strip())
            except (ValueError, IndexError):
                lat = lon = None

            # ── Parse datetime → UTC ───────────────────────────────────────
            obs_date = parts[1].strip()  # MM/DD/YY
            obs_time = parts[2].strip()  # HH:MM
            tz_abbr = parts[3].strip()  # EDT / CDT / …

            observed_utc = _local_to_utc(obs_date, obs_time, tz_abbr)
            if observed_utc is None:
                logger.debug(
                    "Line %d: could not parse datetime '%s %s %s'",
                    lineno,
                    obs_date,
                    obs_time,
                    tz_abbr,
                )
                continue

            # ── Category ───────────────────────────────────────────────────
            cat_name = parts[13].strip() if len(parts) > 13 else aqi_category(aqi_val)
            cat_number = _CATEGORY_NUMBERS.get(cat_name.lower(), 0)

            observations.append(
                {
                    "ReportingArea": parts[7].strip(),
                    "StateCode": parts[8].strip().upper(),
                    "Latitude": lat,
                    "Longitude": lon,
                    # Normalised to YYYY-MM-DD so _parse_observed_at in the task works
                    "DateObserved": observed_utc.strftime("%Y-%m-%d"),
                    "HourObserved": observed_utc.hour,
                    "LocalTimeZone": tz_abbr,
                    "ParameterName": parts[11].strip(),
                    "AQI": aqi_val,
                    "Category": {
                        "Number": cat_number,
                        "Name": cat_name,
                    },
                }
            )

        logger.info(
            "Flat-file parsed: %d current primary observations returned.",
            len(observations),
        )
        return observations
