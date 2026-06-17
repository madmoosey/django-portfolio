from datetime import timedelta

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from django.contrib.gis.db.models.functions import Centroid
from django.core.cache import cache
from django.db.models import Max
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.api.permissions import CanTriggerRecompute
from apps.geodata.models import County
from apps.ingest.tasks.analysis_tasks import predict_county_risk_scores

from .models import CountyRiskScore, MLModel, RiskTrend
from .serializers import CountyRiskScoreSerializer, MLModelSerializer, RiskTrendSerializer

# Risk types served by the predictions GeoJSON endpoint
_PREDICTION_RISK_TYPES = {
    "air_quality",
    "severe_weather",
    "hurricane",
    "tornado",
    "heat_wave",
    "wildfire",
}
# Layer is shown once >= this fraction of counties have scores
_READINESS_THRESHOLD = 0.5
# Cache key prefix and TTL for the predictions endpoint
_CACHE_TTL = 3600  # 1 hour
# Default min_score — only Moderate (40+) and above are shown
_DEFAULT_MIN_SCORE = 40
# Fields fetched from the DB for GeoJSON serialisation (avoids pulling ALL columns)
_SCORE_ONLY_FIELDS = (
    "id",
    "score",
    "confidence",
    "computed_at",
    "factors",
    "data_window_start",
    "data_window_end",
    "risk_type",
    "county__name",
    "county__fips_code",
    "county__state__abbreviation",
    "county__geometry",
)


def _build_features(scores):
    """Shared feature-builder — converts an annotated QS to a list of GeoJSON Feature dicts."""
    features = []
    for s in scores:
        if s.centroid is None:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(s.centroid.x, 5), round(s.centroid.y, 5)],
                },
                "properties": {
                    "county_name": s.county.name,
                    "state": s.county.state.abbreviation if s.county.state else None,
                    "fips": s.county.fips_code,
                    "risk_type": s.risk_type,
                    "score": float(s.score),
                    "confidence": float(s.confidence),
                    "factors": s.factors,
                    "data_window_start": (
                        s.data_window_start.isoformat() if s.data_window_start else None
                    ),
                    "data_window_end": s.data_window_end.isoformat() if s.data_window_end else None,
                    "computed_at": s.computed_at.isoformat(),
                },
            }
        )
    return features


def _scores_qs(risk_type, latest_run, min_score):
    """Optimised queryset: only() the columns we need + annotate centroid."""
    return (
        CountyRiskScore.objects.filter(
            risk_type=risk_type, computed_at=latest_run, score__gte=min_score
        )
        .select_related("county", "county__state")
        .only(*_SCORE_ONLY_FIELDS)
        .annotate(centroid=Centroid("county__geometry"))
        .order_by("-score")  # highest-risk first — better for map rendering priority
    )


@extend_schema(tags=["Analysis - Risk Scores"])
class CountyRiskScoreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CountyRiskScore.objects.select_related("county", "county__state").all()
    serializer_class = CountyRiskScoreSerializer
    filterset_fields = ["risk_type", "county__fips_code", "county__state__abbreviation"]

    @extend_schema(
        summary="Trigger Risk Recomputation",
        description="Admin-only endpoint to trigger an async Celery task that recomputes risk scores.",
        responses={202: OpenApiResponse(description="Recomputation started")},
    )
    @action(detail=False, methods=["post"], permission_classes=[CanTriggerRecompute])
    def recompute(self, request):
        """Triggers the Celery task to recompute all county risk scores."""
        predict_county_risk_scores.delay()
        return Response({"status": "Recomputation task queued."}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        summary="Risk Predictions GeoJSON",
        description=(
            "Returns county-centroid GeoJSON FeatureCollection for the requested risk_type. "
            "Scores >= min_score (default 40 = Moderate+). Cached 1 h."
        ),
        parameters=[
            OpenApiParameter(
                "risk_type",
                str,
                required=True,
                description=f"One of: {sorted(_PREDICTION_RISK_TYPES)}",
            ),
            OpenApiParameter(
                "min_score",
                float,
                required=False,
                description=f"Only return counties with score >= this value (default {_DEFAULT_MIN_SCORE})",
            ),
        ],
    )
    @action(detail=False, url_path="predictions-geojson", url_name="predictions-geojson")
    def predictions_geojson(self, request):
        """
        Returns a GeoJSON FeatureCollection of county centroids annotated with
        ML risk scores for the requested risk type.
        """
        risk_type = request.query_params.get("risk_type", "")
        if risk_type not in _PREDICTION_RISK_TYPES:
            return Response(
                {"error": f"risk_type must be one of {sorted(_PREDICTION_RISK_TYPES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            min_score = float(request.query_params.get("min_score", _DEFAULT_MIN_SCORE))
        except (ValueError, TypeError):
            min_score = float(_DEFAULT_MIN_SCORE)

        cache_key = f"predictions_geojson:{risk_type}:{int(min_score)}"
        cached = cache.get(cache_key)
        if cached:
            return JsonResponse(cached)

        total_counties = County.objects.filter(state__isnull=False).count()

        latest_run = CountyRiskScore.objects.filter(risk_type=risk_type).aggregate(
            latest=Max("computed_at")
        )["latest"]

        if not latest_run:
            payload = {
                "type": "FeatureCollection",
                "features": [],
                "data_ready": False,
                "scored_counties": 0,
                "total_counties": total_counties,
                "phase": "no_data",
            }
            return JsonResponse(payload)

        features = _build_features(_scores_qs(risk_type, latest_run, min_score))
        scored_counties = len(features)
        data_ready = (
            total_counties > 0 and (scored_counties / total_counties) >= _READINESS_THRESHOLD
        )
        phase = (
            "xgboost"
            if (features and features[0]["properties"]["confidence"] > 50)
            else "rule_based"
        )

        payload = {
            "type": "FeatureCollection",
            "features": features,
            "data_ready": data_ready,
            "scored_counties": scored_counties,
            "total_counties": total_counties,
            "phase": phase,
        }
        cache.set(cache_key, payload, _CACHE_TTL)
        return JsonResponse(payload)

    @extend_schema(
        summary="Batch Risk Predictions GeoJSON",
        description=(
            "Returns all 6 risk-type GeoJSON FeatureCollections in a single request. "
            "Use this instead of 6 individual calls. min_score defaults to 40 (Moderate+). "
            "Response is cached 1 h per min_score value."
        ),
        parameters=[
            OpenApiParameter(
                "min_score",
                float,
                required=False,
                description=f"Minimum score threshold (default {_DEFAULT_MIN_SCORE})",
            ),
        ],
    )
    @action(
        detail=False,
        url_path="predictions-geojson-batch",
        url_name="predictions-geojson-batch",
        methods=["get"],
    )
    def predictions_geojson_batch(self, request):
        """
        Returns all 6 prediction layers in one JSON payload:
        { layers: { air_quality: <FeatureCollection>, severe_weather: ..., ... } }
        Total_counties is fetched once and shared across all types.
        """
        try:
            min_score = float(request.query_params.get("min_score", _DEFAULT_MIN_SCORE))
        except (ValueError, TypeError):
            min_score = float(_DEFAULT_MIN_SCORE)

        cache_key = f"predictions_geojson_batch:{int(min_score)}"
        cached = cache.get(cache_key)
        if cached:
            return JsonResponse(cached)

        total_counties = County.objects.filter(state__isnull=False).count()

        # Fetch the latest run timestamp for all types in a single aggregation
        from django.db.models import Max as _Max

        latest_runs = {
            row["risk_type"]: row["latest"]
            for row in (
                CountyRiskScore.objects.filter(risk_type__in=_PREDICTION_RISK_TYPES)
                .values("risk_type")
                .annotate(latest=_Max("computed_at"))
            )
        }

        layers = {}
        for risk_type in sorted(_PREDICTION_RISK_TYPES):
            latest_run = latest_runs.get(risk_type)
            if not latest_run:
                layers[risk_type] = {
                    "type": "FeatureCollection",
                    "features": [],
                    "data_ready": False,
                    "scored_counties": 0,
                    "total_counties": total_counties,
                    "phase": "no_data",
                }
                continue

            features = _build_features(_scores_qs(risk_type, latest_run, min_score))
            scored_counties = len(features)
            # data_ready uses total scored (including below min_score) for the threshold check
            total_scored = CountyRiskScore.objects.filter(
                risk_type=risk_type, computed_at=latest_run
            ).count()
            data_ready = (
                total_counties > 0 and (total_scored / total_counties) >= _READINESS_THRESHOLD
            )
            phase = (
                "xgboost"
                if (features and features[0]["properties"]["confidence"] > 50)
                else "rule_based"
            )

            layers[risk_type] = {
                "type": "FeatureCollection",
                "features": features,
                "data_ready": data_ready,
                "scored_counties": scored_counties,
                "total_counties": total_counties,
                "phase": phase,
            }

        payload = {"layers": layers, "min_score": min_score}
        cache.set(cache_key, payload, _CACHE_TTL)
        return JsonResponse(payload)


@extend_schema(tags=["Analysis - Trends"])
class RiskTrendViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RiskTrend.objects.all()
    serializer_class = RiskTrendSerializer
    filterset_fields = ["risk_type", "county__fips_code"]


@extend_schema(tags=["Analysis - Models"])
class MLModelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer
    filterset_fields = ["risk_type", "is_active"]
