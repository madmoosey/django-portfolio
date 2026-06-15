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
