from django.http import JsonResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from .models import AirQualityObservation
from .serializers import AirQualityObservationGeoSerializer, AirQualityObservationSerializer


class AirQualityObservationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Returns the most recent primary AQI readings (Moderate or worse)
    across all US reporting areas.

    Default ordering: highest AQI first, then most recent observation.

    Supports filtering by:
      - state__abbreviation  (e.g. ?state__abbreviation=CA)
      - aqi_category         (e.g. ?aqi_category=Unhealthy)
      - pollutant            (e.g. ?pollutant=PM2.5)

    Extra actions:
      GET /api/v1/air-quality/observations/geojson/
          Returns a bare GeoJSON FeatureCollection (no pagination envelope)
          using the PostGIS PointField as geometry. Intended for MapLibre.
    """

    queryset = AirQualityObservation.objects.select_related("state", "county").order_by(
        "-aqi", "-observed_at"
    )
    serializer_class = AirQualityObservationSerializer
    filterset_fields = ["state__abbreviation", "aqi_category", "pollutant"]
    ordering_fields = ["aqi", "observed_at"]
    ordering = ["-aqi", "-observed_at"]

    @action(detail=False, url_path="geojson", url_name="geojson")
    def geojson(self, request):
        """
        Return all current AQ observations as a bare GeoJSON FeatureCollection.

        Filters out observations with no PostGIS geometry (location IS NULL).
        Does NOT paginate — the full dataset is returned so MapLibre can
        render all point markers in a single request.

        Supports the same query-string filters as the list endpoint.
        """
        qs = (
            self.filter_queryset(self.get_queryset())
            .exclude(location__isnull=True)
            .select_related("state", "county")
        )

        serializer = AirQualityObservationGeoSerializer(qs, many=True)

        # Build a bare FeatureCollection — no DRF pagination wrapper so
        # MapLibre can consume it directly as a GeoJSON source.
        feature_collection = {
            "type": "FeatureCollection",
            "features": serializer.data,
        }
        return JsonResponse(feature_collection)
