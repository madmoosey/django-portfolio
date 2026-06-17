"""
Tests for apps.ingest.clients.airnow_client.

Covers: aqi_category(), _local_to_utc(), and AirNowClient.get_current_observations()
guard paths + field normalisation.  No real HTTP calls — network is patched.
"""

from datetime import timezone
from unittest.mock import MagicMock, patch

import requests

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
        self.assertEqual(aqi_category(500), "Hazardous")
        self.assertEqual(aqi_category(999), "Hazardous")


class TestLocalToUtc(TestCase):
    """_local_to_utc() parses flat-file timestamps properly."""

    def test_valid_parsing(self):
        utc = _local_to_utc("06/16/26", "14:00", "PDT")
        self.assertIsNotNone(utc)
        self.assertEqual(utc.hour, 21)  # PDT is UTC-7, so 14+7 = 21

    def test_invalid_parsing(self):
        self.assertIsNone(_local_to_utc("bad", "time", "PDT"))


class TestAirNowClientGetCurrentObservations(TestCase):
    """get_current_observations() response handling."""

    def setUp(self):
        self.client = AirNowClient()

    @patch("apps.ingest.clients.airnow_client.requests.Session.get")
    def test_raises_on_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("Network error")
        with self.assertRaises(requests.RequestException):
            self.client.get_current_observations()

    @patch("apps.ingest.clients.airnow_client.requests.Session.get")
    def test_normalises_flat_file_format(self, mock_get):
        """Flat file format is correctly parsed into normalised dicts."""
        mock_resp = MagicMock()
        mock_resp.content = b"06/16/26|06/16/26|14:00|PDT|0|O|Y|Los Angeles|CA|34.05|-118.24|PM2.5|120|Unhealthy for Sensitive Groups|No||Agency\n"
        mock_get.return_value = mock_resp

        result = self.client.get_current_observations()

        self.assertEqual(len(result), 1)
        obs = result[0]
        self.assertEqual(obs["ReportingArea"], "Los Angeles")
        self.assertEqual(obs["StateCode"], "CA")
        self.assertEqual(obs["AQI"], 120)
        self.assertEqual(obs["ParameterName"], "PM2.5")
        self.assertEqual(obs["Category"]["Number"], 3)
        self.assertEqual(obs["Category"]["Name"], "Unhealthy for Sensitive Groups")
        self.assertEqual(obs["Latitude"], 34.05)
        self.assertEqual(obs["Longitude"], -118.24)

    @patch("apps.ingest.clients.airnow_client.requests.Session.get")
    def test_ignores_non_current_or_forecast_rows(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.content = b"""06/16/26|06/16/26|14:00|PDT|1|O|Y|Future|CA|0|0|PM2.5|120|Good|No||Agency
06/16/26|06/16/26|14:00|PDT|0|F|Y|Forecast|CA|0|0|PM2.5|120|Good|No||Agency
06/16/26|06/16/26|14:00|PDT|0|O|N|Secondary|CA|0|0|PM2.5|120|Good|No||Agency
"""
        mock_get.return_value = mock_resp

        result = self.client.get_current_observations()
        self.assertEqual(len(result), 0)

    @patch("apps.ingest.clients.airnow_client.requests.Session.get")
    def test_missing_or_bad_aqi(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.content = b"06/16/26|06/16/26|14:00|PDT|0|O|Y|Los Angeles|CA|34.05|-118.24|PM2.5|-1|Good|No||Agency\n"
        mock_get.return_value = mock_resp

        result = self.client.get_current_observations()
        self.assertEqual(len(result), 0)
