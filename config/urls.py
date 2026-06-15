"""
ArborWatch — URL Configuration.

API-first architecture. All endpoints are under /api/v1/.
Admin interface at /admin/.
API documentation at /api/docs/ and /api/redoc/.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.views import HealthCheckView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Health Check
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

# API v1 Router
from rest_framework.routers import DefaultRouter
from apps.geodata.viewsets import StateViewSet, CountyViewSet
from apps.deforestation.viewsets import (
    TreeCoverBaselineViewSet,
    TreeCoverLossViewSet,
    DeforestationAlertViewSet,
)

from apps.weather.viewsets import WeatherStationViewSet, TemperatureObservationViewSet
from apps.storms.viewsets import StormEventViewSet, ActiveAlertViewSet

api_v1_router = DefaultRouter()
api_v1_router.register(r"geodata/states", StateViewSet, basename="state")
api_v1_router.register(r"geodata/counties", CountyViewSet, basename="county")
api_v1_router.register(
    r"deforestation/baselines", TreeCoverBaselineViewSet, basename="treecoverbaseline"
)
api_v1_router.register(r"deforestation/loss", TreeCoverLossViewSet, basename="treecoverloss")
api_v1_router.register(
    r"deforestation/alerts", DeforestationAlertViewSet, basename="deforestationalert"
)
api_v1_router.register(r"weather/stations", WeatherStationViewSet, basename="weatherstation")
api_v1_router.register(
    r"weather/observations", TemperatureObservationViewSet, basename="temperatureobservation"
)
api_v1_router.register(r"storms/events", StormEventViewSet, basename="stormevent")
api_v1_router.register(r"storms/alerts", ActiveAlertViewSet, basename="activealert")

urlpatterns += [
    path("api/v1/", include(api_v1_router.urls)),
]

# Serve static/media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Debug toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns

# Admin site customization
admin.site.site_header = "ArborWatch Administration"
admin.site.site_title = "ArborWatch Admin"
admin.site.index_title = "Dashboard"
