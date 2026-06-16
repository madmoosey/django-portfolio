import logging

from django.conf import settings

from .base import BaseClient

logger = logging.getLogger(__name__)


class NOAAClient(BaseClient):
    """Client for NOAA APIs (NCEI Climate Data Online & NWS Active Alerts)."""

    def __init__(self):
        super().__init__(base_url="")
        self.cdo_token = getattr(settings, "NOAA_CDO_TOKEN", None)

    def _get_cdo_headers(self):
        headers = {}
        if self.cdo_token:
            headers["token"] = self.cdo_token
        return headers

    def get_daily_summaries(self, station_id, start_date, end_date):
        """Fetch daily temperature and precipitation summaries for a given station."""
        if not self.cdo_token:
            logger.warning("No NOAA_CDO_TOKEN found, returning mocked daily summaries.")
            return self._get_mocked_daily_summaries(station_id, start_date, end_date)

        self.base_url = settings.NOAA_NCEI_BASE_URL.rstrip("/")

        params = {
            "dataset": "daily-summaries",
            "stations": station_id,
            "startDate": start_date,
            "endDate": end_date,
            "dataTypes": "TMAX,TMIN,PRCP",
            "format": "json",
            "units": "metric",
        }

        try:
            return self.get("", params=params, headers=self._get_cdo_headers())
        except Exception as e:
            logger.error(f"NOAA CDO API Error for station {station_id}: {e}")
            return None

    def _get_raw_response(self, endpoint, params=None, headers=None):
        """Make a GET request and return the raw response text (not JSON-decoded)."""
        import requests as _requests

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"GET (raw) {url}")
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except _requests.exceptions.RequestException as exc:
            logger.error(f"Error fetching {url}: {exc}")
            raise

    def get_storm_events_csv(self, start_date, end_date, limit=1000, offset=1):
        """
        Fetch Storm Events data from NOAA CDO as CSV text.

        Args:
            start_date: ISO date string, e.g. '2022-01-01'
            end_date:   ISO date string, e.g. '2022-12-31'
            limit:      Max records per request (CDO max is 1000).
            offset:     Starting record offset (1-indexed).

        Returns:
            str: Raw CSV text, or None on failure.
        """
        if not self.cdo_token:
            logger.warning("NOAA_CDO_TOKEN not set; cannot fetch Storm Events CSV.")
            return None

        self.base_url = getattr(
            __import__("django.conf", fromlist=["settings"]).settings,
            "NOAA_NCEI_BASE_URL",
            "https://www.ncdc.noaa.gov/cdo-web/api/v2",
        ).rstrip("/")

        params = {
            "datasetid": "STORM_EVENTS",
            "startdate": start_date,
            "enddate": end_date,
            "limit": limit,
            "offset": offset,
            "format": "csv",
            "includemetadata": "true",
        }

        try:
            return self._get_raw_response("data", params=params, headers=self._get_cdo_headers())
        except Exception as exc:
            logger.error(f"NOAA CDO Storm Events API error: {exc}")
            return None

    def get_stations(self, dataset_id="GHCND", country_code="US", limit=1000):
        """
        Fetch all weather station metadata from the NOAA CDO /stations endpoint.

        Paginates automatically until all results are collected or the CDO
        returns fewer records than the requested page size.

        Args:
            dataset_id (str): CDO dataset to filter by. Defaults to 'GHCND'
                (Global Historical Climatology Network – Daily), which is the
                dataset used by get_daily_summaries().
            country_code (str): ISO country code to restrict results.
                Defaults to 'US'.
            limit (int): Records per page (CDO max is 1000).

        Returns:
            list[dict]: All station records, each containing at minimum:
                - 'id':        CDO station ID (e.g. 'GHCND:USW00094728')
                - 'name':      Human-readable station name
                - 'latitude':  float
                - 'longitude': float
                - 'elevation': float | None  (metres)
                - 'mindate':   ISO date string of earliest data
                - 'maxdate':   ISO date string of most recent data
            Returns an empty list if the token is absent or the request fails.
        """
        if not self.cdo_token:
            logger.warning("NOAA_CDO_TOKEN not set; cannot fetch station list.")
            return []

        # CDO metadata API — station listings, dataset info, location lookups.
        # NOTE: This is different from NOAA_NCEI_BASE_URL, which is the
        # data-download service (daily summaries, CSV exports).
        # Metadata API: https://www.ncdc.noaa.gov/cdo-web/api/v2
        self.base_url = getattr(
            settings, "NOAA_CDO_API_BASE_URL", "https://www.ncdc.noaa.gov/cdo-web/api/v2"
        ).rstrip("/")

        all_stations = []
        offset = 1

        while True:
            params = {
                "datasetid": dataset_id,
                "locationid": f"FIPS:{country_code}",
                "limit": limit,
                "offset": offset,
            }

            try:
                response = self.get("stations", params=params, headers=self._get_cdo_headers())
            except Exception as exc:
                logger.error(f"CDO /stations request failed at offset={offset}: {exc}")
                break

            if not response:
                break

            results = response.get("results", [])
            all_stations.extend(results)

            # Stop when the page is smaller than the requested limit — no more pages.
            if len(results) < limit:
                break

            offset += limit

        logger.info(f"Fetched {len(all_stations)} stations from CDO (dataset={dataset_id}).")
        return all_stations

    def get_active_alerts(self):
        """Fetch active severe weather alerts from the National Weather Service."""
        self.base_url = getattr(settings, "NWS_API_BASE_URL", "https://api.weather.gov")
        headers = {"User-Agent": getattr(settings, "NWS_USER_AGENT", "ArborWatch/1.0")}

        try:
            return self.get("alerts/active", headers=headers)
        except Exception as e:
            logger.error(f"NWS API Error fetching alerts: {e}")
            return None

    def _get_mocked_daily_summaries(self, station_id, start_date, end_date):
        """Return fake temperature data for local development."""
        import random
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        data = []
        current = start
        while current <= end:
            tmin = random.uniform(-10.0, 20.0)
            tmax = tmin + random.uniform(5.0, 15.0)
            data.append(
                {
                    "STATION": station_id,
                    "DATE": current.strftime("%Y-%m-%d"),
                    "TMAX": round(tmax, 1),
                    "TMIN": round(tmin, 1),
                    "PRCP": round(random.uniform(0.0, 50.0), 1) if random.random() > 0.8 else 0.0,
                }
            )
            current += timedelta(days=1)
        return data
