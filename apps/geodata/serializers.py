"""
ArborWatch Geodata Serializers.

GeoJSON serializers for state and county models.
"""

from rest_framework_gis.serializers import GeoFeatureModelSerializer

from rest_framework import serializers

from apps.geodata.models import County, State


class StateSerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for US states."""

    class Meta:
        model = State
        geo_field = "geometry"
        fields = (
            "id",
            "fips_code",
            "name",
            "abbreviation",
            "area_sq_km",
            "population",
        )


class CountySerializer(GeoFeatureModelSerializer):
    """GeoJSON serializer for US counties."""

    state_name = serializers.CharField(source="state.name", read_only=True)
    state_abbreviation = serializers.CharField(source="state.abbreviation", read_only=True)

    class Meta:
        model = County
        geo_field = "geometry"
        fields = (
            "id",
            "fips_code",
            "name",
            "state_name",
            "state_abbreviation",
            "area_sq_km",
            "population",
        )
