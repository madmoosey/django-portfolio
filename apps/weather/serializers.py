from rest_framework_gis.serializers import GeoFeatureModelSerializer

from rest_framework import serializers

from .models import TemperatureObservation, WeatherStation


class TemperatureObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemperatureObservation
        fields = ["id", "date", "tmax_celsius", "tmin_celsius", "tavg_celsius", "precipitation_mm"]


class WeatherStationSerializer(GeoFeatureModelSerializer):
    county_name = serializers.CharField(source="county.name", read_only=True)
    state_abbreviation = serializers.CharField(source="county.state.abbreviation", read_only=True)
    observations = TemperatureObservationSerializer(many=True, read_only=True)

    class Meta:
        model = WeatherStation
        geo_field = "location"
        fields = [
            "id",
            "station_id",
            "name",
            "county_name",
            "state_abbreviation",
            "elevation_m",
            "is_active",
            "observations",
        ]
