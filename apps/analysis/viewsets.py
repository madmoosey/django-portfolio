from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.api.permissions import CanTriggerRecompute
from apps.ingest.tasks.analysis_tasks import predict_county_risk_scores

from .models import CountyRiskScore, MLModel, RiskTrend
from .serializers import CountyRiskScoreSerializer, MLModelSerializer, RiskTrendSerializer


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
