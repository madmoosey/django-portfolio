from rest_framework import viewsets
from .models import WeatherStation, TemperatureObservation
from .serializers import WeatherStationSerializer, TemperatureObservationSerializer


class WeatherStationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        WeatherStation.objects.select_related("county", "county__state")
        .prefetch_related("observations")
        .all()
    )
    serializer_class = WeatherStationSerializer
    filterset_fields = ["is_active", "county__fips_code", "county__state__abbreviation"]


class TemperatureObservationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TemperatureObservation.objects.select_related("station").all()
    serializer_class = TemperatureObservationSerializer
    filterset_fields = ["station__station_id", "date"]
