from rest_framework_gis.serializers import GeoFeatureModelSerializer

from rest_framework import serializers

from .models import DeforestationAlert, TreeCoverBaseline, TreeCoverLoss


class TreeCoverBaselineSerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source="county.name", read_only=True)
    state_abbreviation = serializers.CharField(source="county.state.abbreviation", read_only=True)

    class Meta:
        model = TreeCoverBaseline
        fields = [
            "id",
            "county",
            "county_name",
            "state_abbreviation",
            "year",
            "tree_cover_percent",
            "tree_cover_area_ha",
            "data_source",
            "created_at",
            "updated_at",
        ]


class TreeCoverLossSerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source="county.name", read_only=True)
    state_abbreviation = serializers.CharField(source="county.state.abbreviation", read_only=True)

    class Meta:
        model = TreeCoverLoss
        fields = [
            "id",
            "county",
            "county_name",
            "state_abbreviation",
            "year",
            "loss_area_ha",
            "loss_percent",
            "primary_driver",
            "data_source",
            "created_at",
        ]


class DeforestationAlertSerializer(GeoFeatureModelSerializer):
    county_name = serializers.CharField(source="county.name", read_only=True)
    state_abbreviation = serializers.CharField(source="county.state.abbreviation", read_only=True)

    class Meta:
        model = DeforestationAlert
        geo_field = "location"
        fields = [
            "id",
            "alert_date",
            "confidence",
            "county_name",
            "state_abbreviation",
            "alert_type",
            "area_ha",
            "created_at",
        ]
