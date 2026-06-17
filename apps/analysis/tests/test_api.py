"""
Integration tests for the predictions-geojson API endpoint.

Correct URL: /api/v1/analysis/risk-scores/predictions-geojson/
"""

import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from django.utils import timezone

from apps.analysis.models import CountyRiskScore, FeatureSnapshot
from apps.geodata.models import County, State

BASE_URL = "/api/v1/analysis/risk-scores/predictions-geojson/"


def _make_geometry():
    poly = Polygon(((-90, 35), (-89, 35), (-89, 36), (-90, 36), (-90, 35)))
    return MultiPolygon(poly)


def _make_state(fips="99"):
    poly = Polygon(((-100, 25), (-80, 25), (-80, 40), (-100, 40), (-100, 25)))
    return State.objects.create(
        name=f"Test State {fips}",
        abbreviation="TS",
        fips_code=fips,
        geometry=MultiPolygon(poly),
        area_sq_km=Decimal("100000.00"),
    )


def _make_county(state, fips="99001", name="Test County"):
    return County.objects.create(
        name=name,
        fips_code=fips,
        state=state,
        geometry=_make_geometry(),
        area_sq_km=Decimal("1000.00"),
    )


def _make_risk_score(county, risk_type, score=65.0, confidence=40.0, computed_at=None):
    return CountyRiskScore.objects.create(
        county=county,
        risk_type=risk_type,
        score=Decimal(str(score)),
        confidence=Decimal(str(confidence)),
        computed_at=computed_at or timezone.now(),
        factors={"test_factor": 42.0},
        data_window_start=date.today() - timedelta(days=30),
        data_window_end=date.today(),
    )


class PredictionsGeoJSONEndpointTests(TestCase):

    def setUp(self):
        self.state = _make_state()
        self.county = _make_county(self.state)
        self.computed_at = timezone.now()
        for rt in (
            "air_quality",
            "severe_weather",
            "hurricane",
            "tornado",
            "heat_wave",
            "wildfire",
        ):
            _make_risk_score(self.county, rt, score=70.0, computed_at=self.computed_at)

    def _get(self, risk_type="air_quality", extra=""):
        return self.client.get(f"{BASE_URL}?risk_type={risk_type}{extra}")

    def test_returns_200_for_valid_risk_type(self):
        resp = self._get("air_quality")
        self.assertEqual(resp.status_code, 200)

    def test_returns_400_for_invalid_risk_type(self):
        resp = self._get("volcanic_eruption")
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertIn("error", data)

    def test_geojson_structure(self):
        resp = self._get("air_quality")
        data = json.loads(resp.content)
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertIn("features", data)
        self.assertIn("data_ready", data)
        self.assertIn("scored_counties", data)
        self.assertIn("total_counties", data)
        self.assertIn("phase", data)

    def test_feature_has_required_properties(self):
        resp = self._get("air_quality")
        data = json.loads(resp.content)
        self.assertGreater(len(data["features"]), 0)
        props = data["features"][0]["properties"]
        for field in (
            "county_name",
            "state",
            "fips",
            "risk_type",
            "score",
            "confidence",
            "factors",
            "computed_at",
        ):
            self.assertIn(field, props, f"Missing property: {field}")

    def test_feature_geometry_is_point(self):
        resp = self._get("air_quality")
        data = json.loads(resp.content)
        feat = data["features"][0]
        self.assertEqual(feat["geometry"]["type"], "Point")
        self.assertEqual(len(feat["geometry"]["coordinates"]), 2)

    def test_all_six_risk_types_return_200(self):
        for rt in (
            "air_quality",
            "severe_weather",
            "hurricane",
            "tornado",
            "heat_wave",
            "wildfire",
        ):
            resp = self._get(rt)
            self.assertEqual(resp.status_code, 200, f"Failed for {rt}")

    def test_all_six_risk_types_return_data(self):
        for rt in (
            "air_quality",
            "severe_weather",
            "hurricane",
            "tornado",
            "heat_wave",
            "wildfire",
        ):
            resp = self._get(rt)
            data = json.loads(resp.content)
            self.assertGreater(len(data["features"]), 0, f"No features for {rt}")

    def test_min_score_filter_excludes_low_scores(self):
        """Counties with score < min_score should not appear."""
        resp = self._get("air_quality", "&min_score=80")
        data = json.loads(resp.content)
        self.assertEqual(len(data["features"]), 0)

    def test_min_score_filter_includes_matching_scores(self):
        resp = self._get("air_quality", "&min_score=50")
        data = json.loads(resp.content)
        self.assertGreater(len(data["features"]), 0)

    def test_data_ready_false_when_no_scores(self):
        from django.core.cache import cache

        cache.clear()
        CountyRiskScore.objects.all().delete()
        resp = self._get("wildfire")
        data = json.loads(resp.content)
        self.assertFalse(data["data_ready"])
        self.assertEqual(data["features"], [])

    def test_scored_counties_matches_feature_count(self):
        resp = self._get("hurricane")
        data = json.loads(resp.content)
        self.assertEqual(data["scored_counties"], len(data["features"]))

    def test_score_value_in_feature_properties(self):
        resp = self._get("air_quality")
        data = json.loads(resp.content)
        props = data["features"][0]["properties"]
        self.assertAlmostEqual(props["score"], 70.0)


class PredictionsGeoJSONReadinessTests(TestCase):
    """Tests for the data_ready ≥50% threshold."""

    def setUp(self):
        self.state = _make_state(fips="98")
        # 4 counties, score only 3 → 75% → ready
        self.counties = [
            _make_county(self.state, fips=f"9800{i}", name=f"County {i}") for i in range(1, 5)
        ]
        self.computed_at = timezone.now()
        for county in self.counties[:3]:
            _make_risk_score(county, "tornado", score=50.0, computed_at=self.computed_at)

    def test_data_ready_true_when_above_threshold(self):
        from django.core.cache import cache

        cache.clear()
        resp = self.client.get(f"{BASE_URL}?risk_type=tornado")
        data = json.loads(resp.content)
        # 3/4 = 75% ≥ 50%
        self.assertTrue(data["data_ready"])

    def test_data_ready_false_when_below_threshold(self):
        from django.core.cache import cache

        cache.clear()
        # Remove 2 → 1/4 = 25% < 50%
        CountyRiskScore.objects.filter(county__in=self.counties[1:3]).delete()
        resp = self.client.get(f"{BASE_URL}?risk_type=tornado")
        data = json.loads(resp.content)
        self.assertFalse(data["data_ready"])
