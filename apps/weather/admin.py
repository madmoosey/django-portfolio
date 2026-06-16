from django.contrib import admin

from .models import TemperatureObservation, WeatherStation


@admin.register(WeatherStation)
class WeatherStationAdmin(admin.ModelAdmin):
    pass


@admin.register(TemperatureObservation)
class TemperatureObservationAdmin(admin.ModelAdmin):
    pass
