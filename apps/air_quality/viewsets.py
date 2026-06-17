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

    # US stations only: exclude international reporting areas whose state FK
    # could not be resolved against the geodata_state table.
    queryset = (
        AirQualityObservation.objects.select_related("state", "county")
        .filter(state__isnull=False)
        .order_by("-aqi", "-observed_at")
    )
    serializer_class = AirQualityObservationSerializer
    filterset_fields = ["state__abbreviation", "aqi_category", "pollutant"]
    ordering_fields = ["aqi", "observed_at"]
    ordering = ["-aqi", "-observed_at"]

    @action(detail=False, url_path="geojson", url_name="geojson")
    def geojson(self, request):
        """
        Return all current US AQ observations as a bare GeoJSON FeatureCollection.

        Filters:
          - location IS NOT NULL — only stations with PostGIS coordinates
          - state IS NOT NULL    — only US reporting areas (drops international
                                   AirNow stations whose state FK couldn't be
                                   resolved against the geodata_state table)

        Does NOT paginate — the full dataset is returned so MapLibre can render
        all point markers in a single request.

        NOTE: GeoFeatureModelSerializer(many=True).data already returns a
        FeatureCollection dict, so we return it directly rather than wrapping it
        inside another {"type": "FeatureCollection", "features": <FC>} envelope
        (which would make .features an object, not an array).
        """
        qs = (
            self.filter_queryset(self.get_queryset())
            .exclude(location__isnull=True)
            .exclude(state__isnull=True)  # US stations only
            .select_related("state", "county")
        )

        serializer = AirQualityObservationGeoSerializer(qs, many=True)

        # serializer.data is already a FeatureCollection — return it directly.
        return JsonResponse(dict(serializer.data))
