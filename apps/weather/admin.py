from django.contrib import admin
from .models import WeatherStation, TemperatureObservation

@admin.register(WeatherStation)
class WeatherStationAdmin(admin.ModelAdmin):
    pass

@admin.register(TemperatureObservation)
class TemperatureObservationAdmin(admin.ModelAdmin):
    pass

