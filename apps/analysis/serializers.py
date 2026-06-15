from rest_framework import serializers

from .models import CountyRiskScore, MLModel, RiskTrend


class CountyRiskScoreSerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source="county.name", read_only=True)
    state_abbreviation = serializers.CharField(source="county.state.abbreviation", read_only=True)

    class Meta:
        model = CountyRiskScore
        fields = [
            "id",
            "county",
            "county_name",
            "state_abbreviation",
            "risk_type",
            "score",
            "confidence",
            "computed_at",
            "factors",
            "data_window_start",
            "data_window_end",
        ]


class RiskTrendSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskTrend
        fields = ["id", "county", "risk_type", "month", "avg_score", "delta_from_previous"]


class MLModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MLModel
        fields = ["id", "name", "version", "risk_type", "is_active", "metrics", "created_at"]
