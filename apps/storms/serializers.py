from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import StormEvent, ActiveAlert


class StormEventSerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source="county.name", read_only=True)
    state_abbreviation = serializers.CharField(source="state.abbreviation", read_only=True)

    class Meta:
        model = StormEvent
        fields = [
            "id",
            "event_id",
            "event_type",
            "begin_date",
            "end_date",
            "state_abbreviation",
            "county_name",
            "magnitude",
            "magnitude_type",
            "deaths_direct",
            "injuries_direct",
            "damage_property_usd",
            "damage_crops_usd",
        ]


class ActiveAlertSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = ActiveAlert
        geo_field = "geometry"
        fields = [
            "id",
            "alert_id",
            "event_type",
            "severity",
            "urgency",
            "certainty",
            "headline",
            "effective",
            "expires",
            "affected_zones",
        ]
