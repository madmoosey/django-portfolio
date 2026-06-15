"""
ArborWatch Geodata ViewSets.

Read-only endpoints returning GeoJSON data for geographic boundaries.
"""

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import viewsets
from rest_framework_gis.filters import InBBoxFilter

from apps.geodata.filters import CountyFilter, StateFilter
from apps.geodata.models import County, State
from apps.geodata.serializers import CountySerializer, StateSerializer


class StateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows states to be viewed.

    Returns standard GeoJSON `FeatureCollection`.
    Supports bounding box filtering via `?in_bbox=min_lon,min_lat,max_lon,max_lat`.
    """

    queryset = State.objects.all()
    serializer_class = StateSerializer
    filterset_class = StateFilter
    bbox_filter_field = "geometry"
    filter_backends = viewsets.ReadOnlyModelViewSet.filter_backends + [InBBoxFilter]

    # State boundaries rarely change, aggressively cache the list view for 24 hours
    @method_decorator(cache_page(60 * 60 * 24))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CountyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows counties to be viewed.

    Returns standard GeoJSON `FeatureCollection`.
    Supports bounding box filtering via `?in_bbox=min_lon,min_lat,max_lon,max_lat`.
    """

    queryset = County.objects.select_related("state").all()
    serializer_class = CountySerializer
    filterset_class = CountyFilter
    bbox_filter_field = "geometry"
    filter_backends = viewsets.ReadOnlyModelViewSet.filter_backends + [InBBoxFilter]

    # County boundaries rarely change, aggressively cache the list view for 24 hours
    @method_decorator(cache_page(60 * 60 * 24))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
