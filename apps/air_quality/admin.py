from django.contrib import admin

from .models import AirQualityObservation


@admin.register(AirQualityObservation)
class AirQualityObservationAdmin(admin.ModelAdmin):
    list_display = [
        "reporting_area",
        "state",
        "county",
        "aqi",
        "aqi_category",
        "pollutant",
        "observed_at",
    ]
    list_filter = ["aqi_category", "pollutant", "state"]
    search_fields = ["reporting_area", "state__name", "county__name"]
    ordering = ["-aqi", "-observed_at"]
    readonly_fields = ["created_at", "updated_at"]
