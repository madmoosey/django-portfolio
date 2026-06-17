from rest_framework_gis.serializers import GeoFeatureModelSerializer

from rest_framework import serializers

from .models import AirQualityObservation


class AirQualityObservationSerializer(serializers.ModelSerializer):
    """Standard paginated serializer used by the list/detail endpoints."""

    state_name = serializers.CharField(
        source="state.name", read_only=True, allow_null=True, default=None
    )
    state_abbreviation = serializers.CharField(
        source="state.abbreviation", read_only=True, allow_null=True, default=None
    )
    county_name = serializers.CharField(
        source="county.name", read_only=True, allow_null=True, default=None
    )
    county_fips = serializers.CharField(
        source="county.fips_code", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = AirQualityObservation
        fields = [
            "id",
            "reporting_area",
            "state_name",
            "state_abbreviation",
            "county_name",
            "county_fips",
            "latitude",
            "longitude",
            "observed_at",
            "pollutant",
            "aqi",
            "aqi_category",
        ]


class AirQualityObservationGeoSerializer(GeoFeatureModelSerializer):
    """
    GeoJSON FeatureCollection serializer for the /geojson/ map action.

    Uses the PostGIS `location` PointField as the geometry source so that
    MapLibre can render AQ observations as native GeoJSON point features.
    Properties include everything needed for the map popup.

    allow_null=True on FK-traversal fields is required: if state or county is
    NULL, DRF raises SkipField during get_attribute(), which
    GeoFeatureModelSerializer does not catch, causing a 500.
    """

    state_abbreviation = serializers.CharField(
        source="state.abbreviation", read_only=True, allow_null=True, default=None
    )
    county_name = serializers.CharField(
        source="county.name", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = AirQualityObservation
        geo_field = "location"
        fields = [
            "id",
            "reporting_area",
            "state_abbreviation",
            "county_name",
            "latitude",
            "longitude",
            "observed_at",
            "pollutant",
            "aqi",
            "aqi_category",
        ]
