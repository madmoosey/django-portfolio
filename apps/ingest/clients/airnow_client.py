"""
AirNow client — ObservationsByReportingArea endpoint.

Base URL: https://www.airnowapi.org/aq/observation/current/racode

Parameters:
    reportingAreaCode  optional  — omit to get all US reporting areas
    format             required  — application/json
    API_KEY            required

Response fields (camelCase):
    dateObserved         str  — MM/DD/YYYY
    hourObserved         int  — 0-23 local time
    localTimeZone        str  — e.g. 'EDT'
    reportingAreaName    str  — city/area name
    reportingAreaAgency  str  — monitoring agency
    reportingAreaCode    str  — e.g. 'ca084'
    nowcastAQI           int  — observed AQI value
    AQICategoryName      str  — Good / Moderate / Unhealthy … / Hazardous
    parameterName        str  — OZONE / PM2.5 / PM10 / CO / NO2
"""

import logging

from django.conf import settings

from .base import BaseClient

logger = logging.getLogger(__name__)

# AQI categories per EPA breakpoints
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


class AirNowClient(BaseClient):
    """
    Client for the EPA AirNow ObservationsByReportingArea endpoint.

    Endpoint: GET /aq/observation/current/racode
    Docs:     https://docs.airnowapi.org/ObservationsByReportingArea/docs

    Omitting reportingAreaCode returns observations for all US reporting areas.
    Requires a valid AIRNOW_API_KEY in Django settings.
    """

    AIRNOW_BASE_URL = "https://www.airnowapi.org"

    def __init__(self):
        super().__init__(base_url=self.AIRNOW_BASE_URL)
        # Strip whitespace/newlines — .env values sometimes include trailing \n
        raw_key = getattr(settings, "AIRNOW_API_KEY", None) or ""
        self.api_key = raw_key.strip()

    def _base_params(self):
        return {"format": "application/json", "API_KEY": self.api_key}

    def get_current_observations(self, reporting_area_code: str = None) -> list[dict]:
        """
        Fetch current AQI observations from the AirNow reporting-area endpoint.

        When *reporting_area_code* is omitted the API returns observations for
        all US reporting areas in a single response.

        The raw response uses camelCase field names.  This method normalises
        them to the PascalCase/nested shape the ingest task already expects,
        so no changes are required downstream:

            ReportingArea  ← reportingAreaName
            StateCode      ← derived from reportingAreaCode (first two chars)
            Latitude       ← (not in response; set to None)
            Longitude      ← (not in response; set to None)
            DateObserved   ← dateObserved
            HourObserved   ← hourObserved
            LocalTimeZone  ← localTimeZone
            ParameterName  ← parameterName
            AQI            ← nowcastAQI
            Category       ← {Number, Name} from AQICategoryName

        Returns [] if the API key is absent, the request fails, or the
        response is not a JSON array.
        """
        if not self.api_key:
            logger.warning(
                "AIRNOW_API_KEY is not configured. "
                "Register at https://docs.airnowapi.org/account/request."
            )
            return []

        masked = self.api_key[:4] + "****" + self.api_key[-4:] if len(self.api_key) > 8 else "****"
        logger.info(f"AirNow request: key={masked} (len={len(self.api_key)})")

        self.base_url = self.AIRNOW_BASE_URL
        params = {**self._base_params()}
        if reporting_area_code:
            params["reportingAreaCode"] = reporting_area_code

        try:
            result = self.get("aq/observation/current/racode", params=params)
        except ValueError as exc:
            # Non-JSON body — likely an HTML error page from a bad/missing key
            logger.warning(f"AirNow returned a non-JSON response — skipping: {exc}")
            return []
        except Exception as exc:
            logger.error(f"AirNow API error: {exc}")
            raise

        if result is None:
            logger.info("AirNow returned null — no observations available this hour.")
            return []

        if not isinstance(result, list):
            preview = repr(result)[:200]
            logger.warning(f"Unexpected AirNow response type: {type(result)} — {preview}")
            return []

        # Normalise camelCase → expected shape so ingest task is unchanged
        normalised = []
        for rec in result:
            aqi_val = rec.get("nowcastAQI")
            cat_name = (rec.get("AQICategoryName") or "").strip()
            ra_code = (rec.get("reportingAreaCode") or "").strip()

            # AirNow state codes are the first two chars of the area code (e.g. 'ca084' → 'ca')
            # but the response may not include a dedicated state field — derive it from racode
            # or fall back to blank; the ingest task will gracefully handle a missing state.
            state_code = ra_code[:2].upper() if len(ra_code) >= 2 else ""

            normalised.append(
                {
                    "ReportingArea": (rec.get("reportingAreaName") or "").strip(),
                    "StateCode": state_code,
                    # Lat/lon not included in this endpoint's response
                    "Latitude": None,
                    "Longitude": None,
                    "DateObserved": (rec.get("dateObserved") or "").strip(),
                    "HourObserved": rec.get("hourObserved"),
                    "LocalTimeZone": (rec.get("localTimeZone") or "").strip(),
                    "ParameterName": (rec.get("parameterName") or "").strip(),
                    "AQI": aqi_val,
                    "Category": {
                        "Number": self._category_number(cat_name),
                        "Name": cat_name,
                    },
                    # Pass through raw code for debugging
                    "_reportingAreaCode": ra_code,
                }
            )

        logger.info(
            f"AirNow returned {len(normalised)} observations "
            f"({'all areas' if not reporting_area_code else reporting_area_code})."
        )
        return normalised

    @staticmethod
    def _category_number(name: str) -> int:
        """Map AQI category name to its EPA number (1–6)."""
        _MAP = {
            "good": 1,
            "moderate": 2,
            "unhealthy for sensitive groups": 3,
            "unhealthy": 4,
            "very unhealthy": 5,
            "hazardous": 6,
        }
        return _MAP.get(name.lower(), 0)
