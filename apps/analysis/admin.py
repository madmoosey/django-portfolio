from django.contrib import admin

from .models import CountyRiskScore, FeatureSnapshot, MLModel, RiskTrend


@admin.register(CountyRiskScore)
class CountyRiskScoreAdmin(admin.ModelAdmin):
    pass


@admin.register(RiskTrend)
class RiskTrendAdmin(admin.ModelAdmin):
    pass


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    pass


@admin.register(FeatureSnapshot)
class FeatureSnapshotAdmin(admin.ModelAdmin):
    pass
