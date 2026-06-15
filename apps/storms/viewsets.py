from rest_framework import viewsets
from .models import StormEvent, ActiveAlert
from .serializers import StormEventSerializer, ActiveAlertSerializer


class StormEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StormEvent.objects.select_related("state", "county").all()
    serializer_class = StormEventSerializer
    filterset_fields = ["event_type", "state__abbreviation", "county__fips_code"]


class ActiveAlertViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActiveAlert.objects.all()
    serializer_class = ActiveAlertSerializer
    filterset_fields = ["event_type", "severity"]
