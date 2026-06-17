"""
Tests for apps.ingest.clients.airnow_client.

Covers: aqi_category(), AirNowClient._category_number(),
        AirNowClient.get_current_observations() — no-key early return,
        null/non-list response guards, and normalisation logic.
Uses unittest.mock to avoid any real HTTP calls.
"""

from datetime import timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.ingest.clients.airnow_client import AirNowClient, aqi_category


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


class TestAirNowClientCategoryNumber(TestCase):
    """_category_number() maps category name strings to EPA numbers 1-6."""

    def setUp(self):
        with override_settings(AIRNOW_API_KEY="test-key-1234"):
            self.client = AirNowClient()

    def test_known_categories(self):
        cases = [
            ("Good", 1),
            ("Moderate", 2),
            ("Unhealthy for Sensitive Groups", 3),
            ("Unhealthy", 4),
            ("Very Unhealthy", 5),
            ("Hazardous", 6),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(self.client._category_number(name), expected)

    def test_unknown_returns_zero(self):
        self.assertEqual(self.client._category_number("Unknown"), 0)
        self.assertEqual(self.client._category_number(""), 0)


class TestAirNowClientGetCurrentObservations(TestCase):
    """get_current_observations() response handling."""

    @override_settings(AIRNOW_API_KEY="")
    def test_returns_empty_list_when_no_api_key(self):
        client = AirNowClient()
        result = client.get_current_observations()
        self.assertEqual(result, [])

    @override_settings(AIRNOW_API_KEY="valid-test-key-xyz")
    def test_returns_empty_list_on_null_response(self):
        client = AirNowClient()
        with patch.object(client, "get", return_value=None):
            result = client.get_current_observations()
        self.assertEqual(result, [])

    @override_settings(AIRNOW_API_KEY="valid-test-key-xyz")
    def test_returns_empty_list_on_non_list_response(self):
        client = AirNowClient()
        with patch.object(client, "get", return_value={"error": "bad"}):
            result = client.get_current_observations()
        self.assertEqual(result, [])

    @override_settings(AIRNOW_API_KEY="valid-test-key-xyz")
    def test_returns_empty_list_on_value_error(self):
        """ValueError from base client (non-JSON body) → graceful empty return."""
        client = AirNowClient()
        with patch.object(client, "get", side_effect=ValueError("Non-JSON response")):
            result = client.get_current_observations()
        self.assertEqual(result, [])

    @override_settings(AIRNOW_API_KEY="valid-test-key-xyz")
    def test_normalises_response_fields(self):
        """camelCase API response is normalised to the expected PascalCase shape."""
        raw = [
            {
                "reportingAreaName": "Los Angeles",
                "reportingAreaCode": "ca084",
                "nowcastAQI": 120,
                "AQICategoryName": "Unhealthy for Sensitive Groups",
                "parameterName": "PM2.5",
                "dateObserved": "06/16/2026",
                "hourObserved": 14,
                "localTimeZone": "PDT",
            }
        ]
        client = AirNowClient()
        with patch.object(client, "get", return_value=raw):
            result = client.get_current_observations()

        self.assertEqual(len(result), 1)
        obs = result[0]
        self.assertEqual(obs["ReportingArea"], "Los Angeles")
        self.assertEqual(obs["StateCode"], "CA")
        self.assertEqual(obs["AQI"], 120)
        self.assertEqual(obs["ParameterName"], "PM2.5")
        self.assertEqual(obs["Category"]["Number"], 3)
        self.assertEqual(obs["Category"]["Name"], "Unhealthy for Sensitive Groups")
        self.assertIsNone(obs["Latitude"])
        self.assertIsNone(obs["Longitude"])
