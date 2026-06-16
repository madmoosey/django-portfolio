from rest_framework import viewsets

from .models import ActiveAlert, StormEvent
from .serializers import ActiveAlertSerializer, StormEventSerializer


class StormEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StormEvent.objects.select_related("state", "county").all()
    serializer_class = StormEventSerializer
    filterset_fields = ["event_type", "state__abbreviation", "county__fips_code"]


class ActiveAlertViewSet(viewsets.ReadOnlyModelViewSet):
    # Exclude Minor severity at the API level; they are also blocked at ingest.
    queryset = ActiveAlert.objects.exclude(severity__iexact="Minor").order_by(
        "severity", "-effective"
    )
    serializer_class = ActiveAlertSerializer
    filterset_fields = ["event_type", "severity"]
