from rest_framework_gis.serializers import GeoFeatureModelSerializer

from rest_framework import serializers

from .models import AirQualityObservation


class AirQualityObservationSerializer(serializers.ModelSerializer):
    """Standard paginated serializer used by the list/detail endpoints."""

    state_name = serializers.CharField(source="state.name", read_only=True)
    state_abbreviation = serializers.CharField(source="state.abbreviation", read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)
    county_fips = serializers.CharField(source="county.fips_code", read_only=True)

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
    """

    state_abbreviation = serializers.CharField(source="state.abbreviation", read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)

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
