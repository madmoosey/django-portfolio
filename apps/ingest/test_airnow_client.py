"""
Tests for apps.ingest.clients.airnow_client.

Covers: aqi_category(), _local_to_utc(), and AirNowClient.get_current_observations()
guard paths + field normalisation.  No real HTTP calls — network is patched.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.ingest.clients.airnow_client import AirNowClient, _local_to_utc, aqi_category


class TestAqiCategory(TestCase):
    """aqi_category() maps integer AQI to EPA category label."""

    def test_good(self):
        self.assertEqual(aqi_category(0), "Good")
        self.assertEqual(aqi_category(50), "Good")

    def test_moderate(self):
        self.assertEqual(aqi_category(51), "Moderate")
        self.assertEqual(aqi_category(100), "Moderate")

    def test_unhealthy_sensitive(self):
        self.assertEqual(aqi_category(101), "Unhealthy for Sensitive Groups")
        self.assertEqual(aqi_category(150), "Unhealthy for Sensitive Groups")

    def test_unhealthy(self):
        self.assertEqual(aqi_category(151), "Unhealthy")
        self.assertEqual(aqi_category(200), "Unhealthy")

    def test_very_unhealthy(self):
        self.assertEqual(aqi_category(201), "Very Unhealthy")
        self.assertEqual(aqi_category(300), "Very Unhealthy")

    def test_hazardous(self):
        self.assertEqual(aqi_category(301), "Hazardous")
        self.assertEqual(aqi_category(999), "Hazardous")


class TestLocalToUtc(TestCase):
    """_local_to_utc() converts flat-file local datetimes to UTC."""

    def test_edt_offset(self):
        """EDT = UTC-4; 12:00 EDT → 16:00 UTC"""
        result = _local_to_utc("06/16/26", "12:00", "EDT")
        self.assertIsNotNone(result)
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.hour, 16)

    def test_pdt_offset(self):
        """PDT = UTC-7; 09:00 PDT → 16:00 UTC"""
        result = _local_to_utc("06/16/26", "09:00", "PDT")
        self.assertEqual(result.hour, 16)

    def test_unknown_tz_defaults_to_utc(self):
        """Unknown TZ abbreviation falls back to UTC offset 0."""
        result = _local_to_utc("06/16/26", "10:00", "XYZ")
        self.assertEqual(result.hour, 10)

    def test_bad_date_returns_none(self):
        result = _local_to_utc("not-a-date", "12:00", "EDT")
        self.assertIsNone(result)


class TestAirNowClientGetCurrentObservations(TestCase):
    """AirNowClient.get_current_observations() flat-file parsing."""

    # Minimal valid flat-file content with one O/0/Y row
    _FLAT_FILE = (
        "06/16/26|06/16/26|12:00|EDT|0|O|Y|"
        "Los Angeles|CA|34.0522|-118.2437|PM2.5|120|"
        "Unhealthy for Sensitive Groups|No||SCAQMD\n"
        # Forecast row — should be skipped (RecType=F)
        "06/16/26|06/16/26|12:00|EDT|0|F|Y|"
        "Los Angeles|CA|34.0522|-118.2437|OZONE|80|Moderate|No||SCAQMD\n"
        # Secondary pollutant — should be skipped (isPrimary=N)
        "06/16/26|06/16/26|12:00|EDT|0|O|N|"
        "San Diego|CA|32.7157|-117.1611|OZONE|60|Moderate|No||SDAPCD\n"
        # AQI == -1 — should be skipped
        "06/16/26|06/16/26|12:00|EDT|0|O|Y|"
        "Nowhere|CA|36.0|-119.0|PM10|-1|N/A|No||TestAgency\n"
    )

    def _make_response(self, text):
        mock_resp = MagicMock()
        mock_resp.content = text.encode("latin-1")
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_empty_list_on_http_error(self):
        import requests

        client = AirNowClient()
        with patch.object(client._session, "get", side_effect=requests.RequestException("timeout")):
            with self.assertRaises(requests.RequestException):
                client.get_current_observations()

    def test_filters_to_current_primary_observations(self):
        """Only the O/0/Y row should pass all filters."""
        client = AirNowClient()
        with patch.object(
            client._session, "get", return_value=self._make_response(self._FLAT_FILE)
        ):
            result = client.get_current_observations()

        # Only the first valid row should survive all filters
        self.assertEqual(len(result), 1)

    def test_normalises_fields_correctly(self):
        """Returned dict has the shape the ingest task expects."""
        client = AirNowClient()
        with patch.object(
            client._session, "get", return_value=self._make_response(self._FLAT_FILE)
        ):
            result = client.get_current_observations()

        obs = result[0]
        self.assertEqual(obs["ReportingArea"], "Los Angeles")
        self.assertEqual(obs["StateCode"], "CA")
        self.assertAlmostEqual(obs["Latitude"], 34.0522)
        self.assertAlmostEqual(obs["Longitude"], -118.2437)
        self.assertEqual(obs["ParameterName"], "PM2.5")
        self.assertEqual(obs["AQI"], 120)
        self.assertEqual(obs["Category"]["Name"], "Unhealthy for Sensitive Groups")
        self.assertEqual(obs["Category"]["Number"], 3)
        self.assertEqual(obs["LocalTimeZone"], "EDT")
        # 12:00 EDT (UTC-4) → 16:00 UTC
        self.assertEqual(obs["HourObserved"], 16)
        self.assertEqual(obs["DateObserved"], "2026-06-16")
