from rest_framework import viewsets
from .models import TreeCoverBaseline, TreeCoverLoss, DeforestationAlert
from .serializers import (
    TreeCoverBaselineSerializer,
    TreeCoverLossSerializer,
    DeforestationAlertSerializer,
)
from .filters import TreeCoverLossFilter, DeforestationAlertFilter


class TreeCoverBaselineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TreeCoverBaseline.objects.select_related("county", "county__state").all()
    serializer_class = TreeCoverBaselineSerializer
    filterset_fields = ["year", "county__fips_code", "county__state__abbreviation", "data_source"]


class TreeCoverLossViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TreeCoverLoss.objects.select_related("county", "county__state").all()
    serializer_class = TreeCoverLossSerializer
    filterset_class = TreeCoverLossFilter


class DeforestationAlertViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeforestationAlert.objects.select_related("county", "county__state").all()
    serializer_class = DeforestationAlertSerializer
    filterset_class = DeforestationAlertFilter
