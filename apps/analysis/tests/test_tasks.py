"""
Tests for the predict_environmental_risks Celery task.

Uses a real test DB and mocked feature extractors to verify:
  - FeatureSnapshot records are saved for each county
  - CountyRiskScore records are saved for all 6 risk types
  - Phase is 'rule_based' before 30 days of snapshots
  - Return dict has expected shape
  - No crash when county has no AQ/storm data (graceful zeros)
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from django.utils import timezone

from apps.analysis.models import CountyRiskScore, FeatureSnapshot
from apps.geodata.models import County, State

TASK_PATH = "apps.ingest.tasks.analysis_tasks"

# Since extractors are imported inside the task function body,
# we must patch at the source module where the class is defined.
AQ_EXT_PATH = "apps.analysis.features.air_quality_features.AirQualityFeatureExtractor"
SW_EXT_PATH = "apps.analysis.features.severe_weather_features.SevereWeatherFeatureExtractor"
HUR_EXT_PATH = "apps.analysis.features.hurricane_features.HurricaneFeatureExtractor"
TOR_EXT_PATH = "apps.analysis.features.tornado_features.TornadoFeatureExtractor"
HEAT_EXT_PATH = "apps.analysis.features.heat_wave_features.HeatWaveFeatureExtractor"
WF_EXT_PATH = "apps.analysis.features.wildfire_features.WildfireFeatureExtractor"

_ZERO_AQ = {
    "aq_obs_count": 0,
    "aq_max_aqi": 0,
    "aq_mean_aqi": 0,
    "aq_unhealthy_days": 0,
    "aq_pm25_fraction": 0,
}
_ZERO_SW = {
    "sw_alert_count": 0,
    "sw_extreme_count": 0,
    "sw_days_since_last": 90,
    "sw_has_tornado": 0,
    "sw_has_flood": 0,
    "sw_has_thunderstorm": 0,
}
_ZERO_HUR = {
    "hur_historical_count": 0,
    "hur_recent_count": 0,
    "hur_deaths": 0,
    "hur_alert_count": 0,
    "hur_extreme_alert_count": 0,
    "hur_days_since_last_alert": 90,
    "hur_coastal_proximity": 0,
}
_ZERO_TOR = {
    "tor_historical_count": 0,
    "tor_recent_count": 0,
    "tor_deaths": 0,
    "tor_max_ef_score": 0,
    "tor_alert_count": 0,
    "tor_extreme_alert_count": 0,
    "tor_days_since_last_alert": 90,
    "tor_alley_proximity": 0,
}
_ZERO_HEAT = {
    "heat_historical_count": 0,
    "heat_recent_count": 0,
    "heat_deaths": 0,
    "heat_alert_count": 0,
    "heat_extreme_alert_count": 0,
    "heat_days_since_last_alert": 90,
    "heat_southern_proximity": 0,
    "heat_season_factor": 0,
}
_ZERO_WF = {
    "wf_historical_count": 0,
    "wf_recent_count": 0,
    "wf_alert_count": 0,
    "wf_extreme_alert_count": 0,
    "wf_days_since_last_alert": 90,
    "wf_pm25_max_aqi": 0,
    "wf_pm25_smoke_days": 0,
    "wf_western_proximity": 0,
    "wf_season_factor": 0,
}


def _mock_extractor(zero_dict):
    m = MagicMock()
    m.return_value.extract.return_value = zero_dict
    return m


def _poly():
    return Polygon(((-90, 35), (-89, 35), (-89, 36), (-90, 36), (-90, 35)))


def _state(fips="88"):
    poly = Polygon(((-100, 25), (-80, 25), (-80, 40), (-100, 40), (-100, 25)))
    return State.objects.create(
        name=f"Task Test State {fips}",
        abbreviation="TT",
        fips_code=fips,
        geometry=MultiPolygon(poly),
        area_sq_km=Decimal("50000.00"),
    )


def _county(state, fips="88001", name="Task County"):
    return County.objects.create(
        name=name,
        fips_code=fips,
        state=state,
        geometry=MultiPolygon(_poly()),
        area_sq_km=Decimal("500.00"),
    )


class PredictEnvironmentalRisksTaskTests(TestCase):

    def setUp(self):
        self.state = _state()
        self.county = _county(self.state)

    def _run_task(self, date_ref=None):
        from apps.ingest.tasks.analysis_tasks import predict_environmental_risks

        with (
            patch(AQ_EXT_PATH, _mock_extractor(_ZERO_AQ)),
            patch(SW_EXT_PATH, _mock_extractor(_ZERO_SW)),
            patch(HUR_EXT_PATH, _mock_extractor(_ZERO_HUR)),
            patch(TOR_EXT_PATH, _mock_extractor(_ZERO_TOR)),
            patch(HEAT_EXT_PATH, _mock_extractor(_ZERO_HEAT)),
            patch(WF_EXT_PATH, _mock_extractor(_ZERO_WF)),
        ):
            return predict_environmental_risks(date_ref=str(date_ref) if date_ref else None)

    def test_task_returns_expected_keys(self):
        result = self._run_task()
        self.assertIn("phase", result)
        self.assertIn("saved", result)
        self.assertIn("date_ref", result)

    def test_phase_is_rule_based_on_first_run(self):
        result = self._run_task()
        self.assertEqual(result["phase"], "rule_based")

    def test_all_six_risk_types_in_result(self):
        result = self._run_task()
        expected = {
            "air_quality",
            "severe_weather",
            "hurricane",
            "tornado",
            "heat_wave",
            "wildfire",
        }
        self.assertEqual(set(result["saved"].keys()), expected)

    def test_county_risk_scores_persisted(self):
        self._run_task()
        # 1 county × 6 risk types
        self.assertEqual(CountyRiskScore.objects.filter(county=self.county).count(), 6)

    def test_feature_snapshot_persisted(self):
        target = date.today()
        self._run_task(date_ref=target)
        snap = FeatureSnapshot.objects.filter(county=self.county, snapshot_date=target).first()
        self.assertIsNotNone(snap)
        self.assertIsInstance(snap.features, dict)

    def test_each_risk_type_scores_all_counties(self):
        result = self._run_task()
        for rt, count in result["saved"].items():
            self.assertEqual(count, 1, f"{rt} should have scored 1 county")

    def test_zero_feature_counties_do_not_crash(self):
        """Task completes without exception when all features are zero."""
        try:
            self._run_task()
        except Exception as exc:
            self.fail(f"Task raised an exception with zero features: {exc}")

    def test_explicit_date_ref_is_respected(self):
        specific_date = date(2026, 6, 1)
        result = self._run_task(date_ref=specific_date)
        self.assertEqual(result["date_ref"], "2026-06-01")
        snap = FeatureSnapshot.objects.filter(
            county=self.county, snapshot_date=specific_date
        ).first()
        self.assertIsNotNone(snap)

    def test_distinct_risk_types_all_present(self):
        """All 6 risk types appear exactly once per county per run."""
        self._run_task()
        risk_types = list(
            CountyRiskScore.objects.filter(county=self.county).values_list("risk_type", flat=True)
        )
        expected = {
            "air_quality",
            "severe_weather",
            "hurricane",
            "tornado",
            "heat_wave",
            "wildfire",
        }
        self.assertEqual(set(risk_types), expected)


class PredictEnvironmentalRisksPhaseTests(TestCase):
    """Tests for the 30-day phase detection logic."""

    def setUp(self):
        self.state = _state(fips="87")
        self.county = _county(self.state, fips="87001", name="Phase County")

    def _seed_snapshots(self, days_back):
        today = date.today()
        combined = {**_ZERO_AQ, **_ZERO_SW, **_ZERO_HUR, **_ZERO_TOR, **_ZERO_HEAT, **_ZERO_WF}
        for i in range(days_back, -1, -1):
            FeatureSnapshot.objects.get_or_create(
                county=self.county,
                snapshot_date=today - timedelta(days=i),
                defaults={"features": combined},
            )

    def _run(self):
        from apps.ingest.tasks.analysis_tasks import predict_environmental_risks

        with (
            patch(AQ_EXT_PATH, _mock_extractor(_ZERO_AQ)),
            patch(SW_EXT_PATH, _mock_extractor(_ZERO_SW)),
            patch(HUR_EXT_PATH, _mock_extractor(_ZERO_HUR)),
            patch(TOR_EXT_PATH, _mock_extractor(_ZERO_TOR)),
            patch(HEAT_EXT_PATH, _mock_extractor(_ZERO_HEAT)),
            patch(WF_EXT_PATH, _mock_extractor(_ZERO_WF)),
        ):
            return predict_environmental_risks()

    def test_rule_based_when_snapshots_under_30_days(self):
        self._seed_snapshots(days_back=10)
        result = self._run()
        self.assertEqual(result["phase"], "rule_based")

    def test_rule_based_when_no_snapshots(self):
        result = self._run()
        self.assertEqual(result["phase"], "rule_based")
