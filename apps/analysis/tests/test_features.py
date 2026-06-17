"""
Tests for the feature extractor classes.

All extractors are tested with mocked DB queries so the test suite
remains fast and has no PostGIS dependency.
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, PropertyMock, patch


def _mock_county(fips="99001", has_geometry=True):
    county = MagicMock()
    county.fips_code = fips
    if has_geometry:
        centroid = MagicMock()
        centroid.x = -95.0  # mid-US → inside tornado alley, east of -100
        centroid.y = 38.0  # mid-US → above 36°, below 35° for hurricane test
        county.geometry = MagicMock()
        county.geometry.centroid = centroid
    else:
        county.geometry = None
    return county


class TestAirQualityFeatureExtractor(unittest.TestCase):
    def _get(self):
        from apps.analysis.features.air_quality_features import AirQualityFeatureExtractor

        return AirQualityFeatureExtractor()

    @patch("apps.air_quality.models.AirQualityObservation")
    def test_returns_zeros_when_no_observations(self, mock_model):
        mock_model.objects.filter.return_value.values_list.return_value = []
        ext = self._get()
        result = ext.extract(_mock_county(), date.today())
        from apps.analysis.features.air_quality_features import AQ_FEATURE_COLS

        for col in AQ_FEATURE_COLS:
            self.assertEqual(result[col], 0)

    @patch("apps.air_quality.models.AirQualityObservation")
    def test_computes_correct_stats(self, mock_model):
        qs = mock_model.objects.filter.return_value
        qs.values_list.return_value = [50, 120, 80, 160]
        qs.filter.return_value.count.return_value = 2  # PM2.5 count

        ext = self._get()
        result = ext.extract(_mock_county(), date.today())

        self.assertEqual(result["aq_obs_count"], 4)
        self.assertEqual(result["aq_max_aqi"], 160)
        self.assertAlmostEqual(result["aq_mean_aqi"], 102.5)
        self.assertEqual(result["aq_unhealthy_days"], 2)  # 120 and 160 > 100
        self.assertAlmostEqual(result["aq_pm25_fraction"], 0.5)

    def test_all_feature_cols_present_in_output(self):
        from apps.analysis.features.air_quality_features import (
            AQ_FEATURE_COLS,
            AirQualityFeatureExtractor,
        )

        with patch("apps.air_quality.models.AirQualityObservation") as mock:
            mock.objects.filter.return_value.values_list.return_value = []
            result = AirQualityFeatureExtractor().extract(_mock_county(), date.today())
        for col in AQ_FEATURE_COLS:
            self.assertIn(col, result)


class TestSevereWeatherFeatureExtractor(unittest.TestCase):
    def _get(self):
        from apps.analysis.features.severe_weather_features import SevereWeatherFeatureExtractor

        return SevereWeatherFeatureExtractor()

    def test_no_geometry_returns_zeros(self):
        from apps.analysis.features.severe_weather_features import SW_FEATURE_COLS

        county = _mock_county(has_geometry=False)
        result = self._get().extract(county, date.today())
        for col in SW_FEATURE_COLS:
            self.assertEqual(result[col], 0)

    @patch("apps.storms.models.ActiveAlert")
    def test_computes_stats_with_alerts(self, mock_alert):
        from datetime import datetime, timezone

        qs = mock_alert.objects.filter.return_value
        qs.count.return_value = 5
        qs.filter.return_value.count.return_value = 2
        last_dt = datetime(2026, 6, 10, tzinfo=timezone.utc)
        qs.order_by.return_value.values_list.return_value.first.return_value = last_dt

        county = _mock_county()
        result = self._get().extract(county, date(2026, 6, 17))

        self.assertEqual(result["sw_alert_count"], 5)
        self.assertEqual(result["sw_extreme_count"], 2)
        self.assertEqual(result["sw_days_since_last"], 7)


class TestHurricaneFeatureExtractor(unittest.TestCase):
    def test_coastal_flag_set_for_gulf_county(self):
        from apps.analysis.features.hurricane_features import HurricaneFeatureExtractor

        county = _mock_county()
        county.geometry.centroid.x = -88.0  # Gulf longitude
        county.geometry.centroid.y = 30.0  # Gulf latitude (< 35)
        ext = HurricaneFeatureExtractor()
        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            result = ext.extract(county, date.today())

        self.assertEqual(result["hur_coastal_proximity"], 1)

    def test_inland_county_has_no_coastal_flag(self):
        from apps.analysis.features.hurricane_features import HurricaneFeatureExtractor

        county = _mock_county()
        county.geometry.centroid.x = -95.0  # inland
        county.geometry.centroid.y = 38.0  # well above 35°

        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            result = HurricaneFeatureExtractor().extract(county, date.today())

        self.assertEqual(result["hur_coastal_proximity"], 0)


class TestTornadoFeatureExtractor(unittest.TestCase):
    def test_alley_flag_set_for_central_us(self):
        from apps.analysis.features.tornado_features import TornadoFeatureExtractor

        county = _mock_county()
        county.geometry.centroid.x = -95.0  # inside alley (-103 to -75)
        county.geometry.centroid.y = 37.0  # inside alley (25 to 50)

        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            result = TornadoFeatureExtractor().extract(county, date.today())

        self.assertEqual(result["tor_alley_proximity"], 1)

    def test_west_coast_county_not_in_alley(self):
        from apps.analysis.features.tornado_features import TornadoFeatureExtractor

        county = _mock_county()
        county.geometry.centroid.x = -120.0  # west of alley
        county.geometry.centroid.y = 37.0

        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            result = TornadoFeatureExtractor().extract(county, date.today())

        self.assertEqual(result["tor_alley_proximity"], 0)


class TestHeatWaveFeatureExtractor(unittest.TestCase):
    def test_season_factor_in_summer(self):
        from apps.analysis.features.heat_wave_features import HeatWaveFeatureExtractor

        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            result = HeatWaveFeatureExtractor().extract(_mock_county(), date(2026, 7, 15))

        self.assertEqual(result["heat_season_factor"], 1)

    def test_season_factor_off_in_winter(self):
        from apps.analysis.features.heat_wave_features import HeatWaveFeatureExtractor

        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            result = HeatWaveFeatureExtractor().extract(_mock_county(), date(2026, 1, 15))

        self.assertEqual(result["heat_season_factor"], 0)


class TestWildfireFeatureExtractor(unittest.TestCase):
    def test_western_flag_set_for_california(self):
        from apps.analysis.features.wildfire_features import WildfireFeatureExtractor

        county = _mock_county()
        county.geometry.centroid.x = -119.0  # California longitude (< -100)

        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
            patch("apps.air_quality.models.AirQualityObservation") as maq,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            maq.objects.filter.return_value.values_list.return_value = []
            result = WildfireFeatureExtractor().extract(county, date.today())

        self.assertEqual(result["wf_western_proximity"], 1)

    def test_eastern_county_not_western(self):
        from apps.analysis.features.wildfire_features import WildfireFeatureExtractor

        county = _mock_county()
        county.geometry.centroid.x = -75.0  # Eastern seaboard (> -100)

        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
            patch("apps.air_quality.models.AirQualityObservation") as maq,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            maq.objects.filter.return_value.values_list.return_value = []
            result = WildfireFeatureExtractor().extract(county, date.today())

        self.assertEqual(result["wf_western_proximity"], 0)

    def test_fire_season_may_through_october(self):
        from apps.analysis.features.wildfire_features import WildfireFeatureExtractor

        county = _mock_county()
        for month in (5, 6, 7, 8, 9, 10):
            with (
                patch("apps.storms.models.StormEvent") as ms,
                patch("apps.storms.models.ActiveAlert") as ma,
                patch("apps.air_quality.models.AirQualityObservation") as maq,
            ):
                for m in (ms, ma):
                    qs = m.objects.filter.return_value
                    qs.filter.return_value.count.return_value = 0
                    qs.count.return_value = 0
                    qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                    qs.order_by.return_value.values_list.return_value.first.return_value = None
                maq.objects.filter.return_value.values_list.return_value = []
                result = WildfireFeatureExtractor().extract(county, date(2026, month, 15))
            self.assertEqual(result["wf_season_factor"], 1, f"Month {month} should be fire season")

    def test_off_season_december(self):
        from apps.analysis.features.wildfire_features import WildfireFeatureExtractor

        county = _mock_county()
        with (
            patch("apps.storms.models.StormEvent") as ms,
            patch("apps.storms.models.ActiveAlert") as ma,
            patch("apps.air_quality.models.AirQualityObservation") as maq,
        ):
            for m in (ms, ma):
                qs = m.objects.filter.return_value
                qs.filter.return_value.count.return_value = 0
                qs.count.return_value = 0
                qs.aggregate.return_value = {"total_deaths": 0, "total_damage": 0}
                qs.order_by.return_value.values_list.return_value.first.return_value = None
            maq.objects.filter.return_value.values_list.return_value = []
            result = WildfireFeatureExtractor().extract(county, date(2026, 12, 15))

        self.assertEqual(result["wf_season_factor"], 0)
