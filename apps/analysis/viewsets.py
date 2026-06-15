from rest_framework import viewsets

from .models import CountyRiskScore, MLModel, RiskTrend
from .serializers import CountyRiskScoreSerializer, MLModelSerializer, RiskTrendSerializer


class CountyRiskScoreViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CountyRiskScore.objects.select_related("county", "county__state").all()
    serializer_class = CountyRiskScoreSerializer
    filterset_fields = ["risk_type", "county__fips_code", "county__state__abbreviation"]


class RiskTrendViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RiskTrend.objects.all()
    serializer_class = RiskTrendSerializer
    filterset_fields = ["risk_type", "county__fips_code"]


class MLModelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MLModel.objects.all()
    serializer_class = MLModelSerializer
    filterset_fields = ["risk_type", "is_active"]
