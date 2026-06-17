"""
Model-level tests for CountyRiskScore and FeatureSnapshot.

Tests:
  - str() representations
  - unique_together constraints
  - Decimal field precision
  - JSON factors field
  - Index configuration
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.analysis.models import CountyRiskScore, FeatureSnapshot, MLModel
from apps.geodata.models import County, State


def _poly():
    return Polygon(((-90, 35), (-89, 35), (-89, 36), (-90, 36), (-90, 35)))


def _make_state(fips="77"):
    poly = Polygon(((-100, 25), (-80, 25), (-80, 40), (-100, 40), (-100, 25)))
    return State.objects.create(
        name=f"Model Test State {fips}",
        abbreviation="MT",
        fips_code=fips,
        geometry=MultiPolygon(poly),
        area_sq_km=Decimal("10000.00"),
    )


def _make_county(state, fips="77001"):
    return County.objects.create(
        name="Model Test County",
        fips_code=fips,
        state=state,
        geometry=MultiPolygon(_poly()),
        area_sq_km=Decimal("200.00"),
    )


class CountyRiskScoreModelTests(TestCase):
    def setUp(self):
        self.state = _make_state()
        self.county = _make_county(self.state)
        self.computed_at = timezone.now()

    def _score(self, risk_type="air_quality", score=55.5):
        return CountyRiskScore.objects.create(
            county=self.county,
            risk_type=risk_type,
            score=Decimal(str(score)),
            confidence=Decimal("40.00"),
            computed_at=self.computed_at,
            factors={"test": 1.0},
            data_window_start=date.today() - timedelta(days=30),
            data_window_end=date.today(),
        )

    def test_str_representation(self):
        s = self._score()
        self.assertIn("Model Test County", str(s))
        self.assertIn("air_quality", str(s))
        self.assertIn("55.5", str(s))

    def test_factors_json_field_round_trips(self):
        s = self._score()
        s.refresh_from_db()
        self.assertEqual(s.factors, {"test": 1.0})

    def test_unique_together_prevents_duplicate(self):
        self._score()
        with self.assertRaises(IntegrityError):
            self._score()  # same county + risk_type + computed_at

    def test_all_six_risk_types_can_be_saved(self):
        for rt in (
            "air_quality",
            "severe_weather",
            "hurricane",
            "tornado",
            "heat_wave",
            "wildfire",
        ):
            CountyRiskScore.objects.create(
                county=self.county,
                risk_type=rt,
                score=Decimal("50.00"),
                confidence=Decimal("40.00"),
                computed_at=timezone.now(),
                factors={},
                data_window_start=date.today() - timedelta(days=30),
                data_window_end=date.today(),
            )
        self.assertEqual(CountyRiskScore.objects.filter(county=self.county).count(), 6)

    def test_score_decimal_precision(self):
        s = self._score(score=99.99)
        s.refresh_from_db()
        self.assertEqual(s.score, Decimal("99.99"))


class FeatureSnapshotModelTests(TestCase):
    def setUp(self):
        self.state = _make_state(fips="66")
        self.county = _make_county(self.state, fips="66001")

    def test_create_snapshot(self):
        snap = FeatureSnapshot.objects.create(
            county=self.county,
            snapshot_date=date.today(),
            features={"aq_obs_count": 10, "wf_season_factor": 1},
        )
        snap.refresh_from_db()
        self.assertEqual(snap.features["aq_obs_count"], 10)

    def test_unique_together_county_date(self):
        FeatureSnapshot.objects.create(
            county=self.county,
            snapshot_date=date.today(),
            features={},
        )
        with self.assertRaises(IntegrityError):
            FeatureSnapshot.objects.create(
                county=self.county,
                snapshot_date=date.today(),
                features={},
            )

    def test_update_or_create_idempotent(self):
        for _ in range(3):
            FeatureSnapshot.objects.update_or_create(
                county=self.county,
                snapshot_date=date.today(),
                defaults={"features": {"run": 1}},
            )
        self.assertEqual(FeatureSnapshot.objects.filter(county=self.county).count(), 1)


class MLModelModelTests(TestCase):
    def test_create_and_str(self):
        m = MLModel.objects.create(
            name="AQ-XGBoost",
            version="1.0",
            risk_type="air_quality",
            is_active=True,
            hyperparameters={"n_estimators": 100},
            metrics={"auc": 0.82},
        )
        self.assertIn("AQ-XGBoost", str(m))
        self.assertIn("Active", str(m))

    def test_inactive_model_str(self):
        m = MLModel.objects.create(
            name="Hurricane-XGBoost",
            version="0.1",
            risk_type="hurricane",
            is_active=False,
        )
        self.assertIn("Inactive", str(m))
