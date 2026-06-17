"""ArborWatch Geodata Admin Configuration."""

from django.contrib.gis import admin

from .models import County, State


@admin.register(State)
class StateAdmin(admin.GISModelAdmin):
    """Admin interface for State models with map widget."""

    list_display = ("name", "abbreviation", "fips_code", "area_sq_km", "population")
    search_fields = ("name", "abbreviation", "fips_code")
    ordering = ("name",)
    list_per_page = 100

    def get_queryset(self, request):
        """Defer geometry columns on the list view — they're only needed in the detail form."""
        qs = super().get_queryset(request)
        if request.resolver_match.url_name == "geodata_state_changelist":
            qs = qs.defer("geometry")
        return qs


@admin.register(County)
class CountyAdmin(admin.GISModelAdmin):
    """Admin interface for County models with map widget.

    Geometry columns are deferred on the list view to prevent OOM-killing
    Gunicorn workers when loading all 3,141 US counties.
    """

    list_display = ("name", "state_name", "fips_code", "area_sq_km", "population")
    search_fields = ("name", "fips_code", "state__abbreviation")
    list_filter = ("state",)
    list_select_related = ("state",)
    ordering = ("state__name", "name")
    list_per_page = 100  # was unlimited — that caused OOM 502s with full geometry

    def get_queryset(self, request):
        """Defer heavy geometry columns on the list view.

        The full MultiPolygon geometries (raw + simplified) can exceed 100 MB for
        all 3,141 counties, causing the Gunicorn worker to be OOM-killed → 502.
        Only the detail/change form needs the geometry (to render the map widget).
        """
        qs = super().get_queryset(request)
        # Only defer on the changelist — the detail form needs geometry for the map widget
        if request.resolver_match.url_name == "geodata_county_changelist":
            qs = qs.defer("geometry", "simplified_geometry")
        return qs

    @admin.display(description="State", ordering="state__name")
    def state_name(self, obj):
        """Return state abbreviation without triggering a geometry fetch via __str__."""
        return obj.state.abbreviation if obj.state_id else "—"
