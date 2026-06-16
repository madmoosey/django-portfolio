from django.contrib import admin
from .models import CountyRiskScore, RiskTrend, MLModel, FeatureSnapshot

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

