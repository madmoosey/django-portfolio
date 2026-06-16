"""
ArborWatch Geodata ViewSets.

Read-only endpoints returning GeoJSON data for geographic boundaries.
"""

import json

from rest_framework_gis.filters import InBBoxFilter
from rest_framework_gis.pagination import GeoJsonPagination

from django.contrib.gis.db.models.functions import AsGeoJSON
from django.db.models import FloatField, Func, IntegerField, OuterRef, Subquery, Value
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import viewsets
from rest_framework.decorators import action

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
    pagination_class = GeoJsonPagination

    # State boundaries rarely change — cache aggressively
    # @method_decorator(cache_page(60 * 60 * 24))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CountyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows counties to be viewed.

    Returns standard GeoJSON `FeatureCollection`.
    Supports bounding box filtering via `?in_bbox=min_lon,min_lat,max_lon,max_lat`.

    Extra actions:
      GET /api/v1/geodata/counties/choropleth/
          Returns a lightweight GeoJSON FeatureCollection with
          ST_SimplifyPreserveTopology geometry and the most recent
          tree-cover-loss annotation per county. Intended for MapLibre.
    """

    queryset = County.objects.select_related("state").all()
    serializer_class = CountySerializer
    filterset_class = CountyFilter
    bbox_filter_field = "geometry"
    filter_backends = viewsets.ReadOnlyModelViewSet.filter_backends + [InBBoxFilter]
    pagination_class = GeoJsonPagination

    # @method_decorator(cache_page(60 * 60 * 24))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=False, url_path="choropleth", url_name="choropleth")
    @method_decorator(cache_page(60 * 30))  # 30-min cache; loss data changes infrequently
    def choropleth(self, request):
        """
        Lightweight county choropleth for the Risk Map.

        Returns a bare GeoJSON FeatureCollection (no DRF pagination wrapper).
        Geometry is simplified server-side via ST_SimplifyPreserveTopology
        (tolerance=0.01°, ~1 km) — roughly 85% smaller than the full county
        endpoint. Each feature's properties include the most recent
        tree-cover-loss hectares and year for choropleth colouring.

        GeoJSON is built manually from SQL annotations rather than via
        GeoFeatureModelSerializer, because annotated fields are not model
        fields and would fail validation.

        Cached 30 minutes.
        """
        from django.contrib.gis.db.models import GeometryField

        from apps.deforestation.models import TreeCoverLoss

        # _STSimplify: wraps ST_SimplifyPreserveTopology(geometry, tolerance)
        # output_field=GeometryField so Django knows it returns geometry.
        class _STSimplify(Func):
            function = "ST_SimplifyPreserveTopology"
            arity = 2
            output_field = GeometryField(srid=4326)

        # Subquery: most recent loss_area_ha per county
        latest_loss = (
            TreeCoverLoss.objects.filter(county=OuterRef("pk"))
            .order_by("-year")
            .values("loss_area_ha")[:1]
        )
        # Subquery: year that loss belongs to
        latest_year = (
            TreeCoverLoss.objects.filter(county=OuterRef("pk")).order_by("-year").values("year")[:1]
        )

        # Annotate each county with:
        #   geojson_str       — ST_AsGeoJSON of the simplified geometry (string)
        #   latest_loss_ha    — most recent loss_area_ha (float | None)
        #   latest_loss_year  — year of that loss record (int | None)
        qs = (
            County.objects.select_related("state").annotate(
                geojson_str=AsGeoJSON(
                    _STSimplify("geometry", Value(0.01)),
                    precision=6,
                ),
                latest_loss_ha=Subquery(latest_loss, output_field=FloatField()),
                latest_loss_year=Subquery(latest_year, output_field=IntegerField()),
            )
            # Only pull the columns we actually need — avoids fetching full geometry
            .only("fips_code", "name", "state")
        )

        features = []
        for county in qs.iterator(chunk_size=500):
            geometry = json.loads(county.geojson_str) if county.geojson_str else None
            loss_ha = float(county.latest_loss_ha) if county.latest_loss_ha is not None else None

            features.append(
                {
                    "type": "Feature",
                    "id": county.fips_code,
                    "geometry": geometry,
                    "properties": {
                        "fips_code": county.fips_code,
                        "name": county.name,
                        "state_abbreviation": county.state.abbreviation,
                        "loss_area_ha": loss_ha,
                        "loss_year": county.latest_loss_year,
                    },
                }
            )

        return JsonResponse(
            {
                "type": "FeatureCollection",
                "count": len(features),
                "features": features,
            }
        )
