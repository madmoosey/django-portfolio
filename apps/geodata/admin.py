"""ArborWatch Geodata Admin Configuration."""

from django.contrib.gis import admin
from .models import State, County


@admin.register(State)
class StateAdmin(admin.GISModelAdmin):
    """Admin interface for State models with map widget."""

    list_display = ("name", "abbreviation", "fips_code", "area_sq_km", "population")
    search_fields = ("name", "abbreviation", "fips_code")
    ordering = ("name",)


@admin.register(County)
class CountyAdmin(admin.GISModelAdmin):
    """Admin interface for County models with map widget."""

    list_display = ("name", "state", "fips_code", "area_sq_km", "population")
    search_fields = ("name", "fips_code")
    list_filter = ("state",)
    ordering = ("state__name", "name")
