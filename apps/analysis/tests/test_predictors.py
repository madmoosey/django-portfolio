"""
Unit tests for the ML predictor classes.

These tests are pure Python — no database, no PostGIS, no Celery.
They verify:
  - Rule-based scoring returns values in the expected 0-100 range
  - score_county() dispatches to rule_based_score() when _trained=False
  - score_county() dispatches to XGBoost predict() when _trained=True
  - Confidence values match the documented constants
  - Zero-feature dicts produce a score of 0 (not an exception)
  - Capped/boundary feature values are handled correctly

Note: rule_based_score() returns a 2-tuple (score, factors).
      score_county() returns a 3-tuple (score, confidence, factors).
"""

import unittest
from unittest.mock import MagicMock

import numpy as np


class TestAirQualityPredictor(unittest.TestCase):
    def _get(self):
        from apps.analysis.ml.air_quality_predictor import AirQualityPredictor

        return AirQualityPredictor()

    def test_rule_based_zero_features_returns_zero(self):
        pred = self._get()
        score, conf, factors = pred.score_county({})
        self.assertEqual(score, 0.0)
        self.assertEqual(conf, 40.0)

    def test_rule_based_max_features_caps_at_100(self):
        from apps.analysis.ml.air_quality_predictor import AirQualityPredictor

        features = {
            "aq_unhealthy_days": 30,
            "aq_max_aqi": 500,
            "aq_mean_aqi": 300,
            "aq_obs_count": 720,
            "aq_pm25_fraction": 1.0,
        }
        score, factors = AirQualityPredictor.rule_based_score(features)
        self.assertLessEqual(score, 100.0)
        self.assertGreater(score, 0.0)

    def test_rule_based_partial_features(self):
        from apps.analysis.ml.air_quality_predictor import AirQualityPredictor

        features = {"aq_unhealthy_days": 10, "aq_max_aqi": 200}
        score, factors = AirQualityPredictor.rule_based_score(features)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        self.assertIn("frequency", factors)
        self.assertIn("severity", factors)

    def test_score_county_returns_tuple_of_three(self):
        pred = self._get()
        result = pred.score_county({"aq_max_aqi": 150, "aq_unhealthy_days": 5})
        self.assertEqual(len(result), 3)

    def test_confidence_is_rule_based_constant_before_training(self):
        from apps.analysis.ml.air_quality_predictor import CONF_RULE_BASED

        pred = self._get()
        _, conf, _ = pred.score_county({})
        self.assertEqual(conf, CONF_RULE_BASED)

    def test_trained_flag_false_by_default(self):
        pred = self._get()
        self.assertFalse(pred._trained)

    def test_xgboost_path_used_when_trained(self):
        """When _trained=True, score_county delegates to predict()."""
        from apps.analysis.ml.air_quality_predictor import (
            CONF_XGBOOST,
            FEATURE_COLS,
            AirQualityPredictor,
        )

        pred = AirQualityPredictor()
        pred._trained = True
        pred.model = MagicMock()
        pred.model.predict_proba.return_value = np.array([[0.3, 0.7]])
        score, conf, _ = pred.score_county({c: 0 for c in FEATURE_COLS})
        self.assertAlmostEqual(score, 70.0)
        self.assertEqual(conf, CONF_XGBOOST)


class TestSevereWeatherPredictor(unittest.TestCase):
    def _get(self):
        from apps.analysis.ml.severe_weather_predictor import SevereWeatherPredictor

        return SevereWeatherPredictor()

    def test_zero_features_score_is_zero(self):
        score, conf, _ = self._get().score_county({})
        self.assertEqual(score, 0.0)

    def test_max_features_caps_at_100(self):
        from apps.analysis.ml.severe_weather_predictor import SevereWeatherPredictor

        features = {
            "sw_alert_count": 100,
            "sw_extreme_count": 50,
            "sw_days_since_last": 0,
            "sw_has_tornado": 1,
            "sw_has_flood": 1,
            "sw_has_thunderstorm": 1,
        }
        score, factors = SevereWeatherPredictor.rule_based_score(features)
        self.assertLessEqual(score, 100.0)

    def test_tornado_bonus_increases_score(self):
        from apps.analysis.ml.severe_weather_predictor import SevereWeatherPredictor

        base = {"sw_alert_count": 10, "sw_days_since_last": 30}
        with_tornado = {**base, "sw_has_tornado": 1}
        s_base, _ = SevereWeatherPredictor.rule_based_score(base)
        s_torn, _ = SevereWeatherPredictor.rule_based_score(with_tornado)
        self.assertGreater(s_torn, s_base)

    def test_rule_based_confidence_constant(self):
        from apps.analysis.ml.severe_weather_predictor import CONF_RULE_BASED

        _, conf, _ = self._get().score_county({})
        self.assertEqual(conf, CONF_RULE_BASED)


class TestHurricanePredictor(unittest.TestCase):
    def _get(self):
        from apps.analysis.ml.hurricane import HurricanePredictor

        return HurricanePredictor()

    def test_zero_features(self):
        score, conf, _ = self._get().score_county({})
        self.assertEqual(score, 0.0)

    def test_coastal_proximity_bonus(self):
        from apps.analysis.ml.hurricane import HurricanePredictor

        no_coast = {"hur_historical_count": 5}
        with_coast = {**no_coast, "hur_coastal_proximity": 1}
        s1, _ = HurricanePredictor.rule_based_score(no_coast)
        s2, _ = HurricanePredictor.rule_based_score(with_coast)
        self.assertGreater(s2, s1)

    def test_score_range(self):
        from apps.analysis.ml.hurricane import HurricanePredictor

        features = {
            "hur_historical_count": 20,
            "hur_recent_count": 3,
            "hur_deaths": 50,
            "hur_alert_count": 5,
            "hur_extreme_alert_count": 2,
            "hur_days_since_last_alert": 10,
            "hur_coastal_proximity": 1,
        }
        score, _ = HurricanePredictor.rule_based_score(features)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)


class TestTornadoPredictor(unittest.TestCase):
    def _get(self):
        from apps.analysis.ml.tornado import TornadoPredictor

        return TornadoPredictor()

    def test_zero_features(self):
        score, conf, _ = self._get().score_county({})
        self.assertEqual(score, 0.0)

    def test_ef5_increases_score_vs_ef0(self):
        from apps.analysis.ml.tornado import TornadoPredictor

        base = {"tor_historical_count": 10}
        ef5 = {**base, "tor_max_ef_score": 5.0}
        s_base, _ = TornadoPredictor.rule_based_score(base)
        s_ef5, _ = TornadoPredictor.rule_based_score(ef5)
        self.assertGreater(s_ef5, s_base)

    def test_alley_proximity_bonus(self):
        from apps.analysis.ml.tornado import TornadoPredictor

        no_alley = {"tor_recent_count": 3}
        in_alley = {**no_alley, "tor_alley_proximity": 1}
        s1, _ = TornadoPredictor.rule_based_score(no_alley)
        s2, _ = TornadoPredictor.rule_based_score(in_alley)
        self.assertGreater(s2, s1)

    def test_factors_dict_present(self):
        from apps.analysis.ml.tornado import TornadoPredictor

        _, factors = TornadoPredictor.rule_based_score({"tor_historical_count": 5})
        self.assertIsInstance(factors, dict)
        self.assertIn("historical", factors)


class TestHeatWavePredictor(unittest.TestCase):
    def _get(self):
        from apps.analysis.ml.heat_wave import HeatWavePredictor

        return HeatWavePredictor()

    def test_zero_features(self):
        score, _, _ = self._get().score_county({})
        self.assertEqual(score, 0.0)

    def test_season_factor_increases_score(self):
        from apps.analysis.ml.heat_wave import HeatWavePredictor

        base = {"heat_historical_count": 5}
        seasonal = {**base, "heat_season_factor": 1}
        s1, _ = HeatWavePredictor.rule_based_score(base)
        s2, _ = HeatWavePredictor.rule_based_score(seasonal)
        self.assertGreater(s2, s1)

    def test_southern_proximity_bonus(self):
        from apps.analysis.ml.heat_wave import HeatWavePredictor

        base = {"heat_recent_count": 2}
        south = {**base, "heat_southern_proximity": 1}
        s1, _ = HeatWavePredictor.rule_based_score(base)
        s2, _ = HeatWavePredictor.rule_based_score(south)
        self.assertGreater(s2, s1)


class TestWildfirePredictor(unittest.TestCase):
    def _get(self):
        from apps.analysis.ml.wildfire_predictor import WildfirePredictor

        return WildfirePredictor()

    def test_zero_features(self):
        score, _, _ = self._get().score_county({})
        self.assertEqual(score, 0.0)

    def test_pm25_smoke_proxy_increases_score(self):
        from apps.analysis.ml.wildfire_predictor import WildfirePredictor

        base = {"wf_historical_count": 2}
        smoke = {**base, "wf_pm25_max_aqi": 300, "wf_pm25_smoke_days": 8}
        s1, _ = WildfirePredictor.rule_based_score(base)
        s2, _ = WildfirePredictor.rule_based_score(smoke)
        self.assertGreater(s2, s1)

    def test_western_proximity_bonus(self):
        from apps.analysis.ml.wildfire_predictor import WildfirePredictor

        base = {"wf_recent_count": 3}
        west = {**base, "wf_western_proximity": 1}
        s1, _ = WildfirePredictor.rule_based_score(base)
        s2, _ = WildfirePredictor.rule_based_score(west)
        self.assertGreater(s2, s1)

    def test_season_factor_increases_score(self):
        from apps.analysis.ml.wildfire_predictor import WildfirePredictor

        base = {"wf_historical_count": 3}
        peak = {**base, "wf_season_factor": 1}
        s1, _ = WildfirePredictor.rule_based_score(base)
        s2, _ = WildfirePredictor.rule_based_score(peak)
        self.assertGreater(s2, s1)

    def test_score_never_exceeds_100(self):
        from apps.analysis.ml.wildfire_predictor import WildfirePredictor

        features = {
            "wf_historical_count": 200,
            "wf_recent_count": 50,
            "wf_alert_count": 50,
            "wf_extreme_alert_count": 20,
            "wf_days_since_last_alert": 0,
            "wf_pm25_max_aqi": 500,
            "wf_pm25_smoke_days": 30,
            "wf_western_proximity": 1,
            "wf_season_factor": 1,
        }
        score, _ = WildfirePredictor.rule_based_score(features)
        self.assertLessEqual(score, 100.0)
