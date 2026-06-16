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
    def choropleth(self, request):
        """
        Lightweight county choropleth for the Risk Map.

        Performance strategy
        --------------------
        1. **Pre-stored geometry**: uses County.simplified_geometry when available
           (populated by the ``build_choropleth_geometry`` Celery task — runs
           automatically every Sunday at 03:00 UTC, or trigger on-demand with
           ``build_choropleth_geometry.delay()``).
           Falls back to ST_SimplifyPreserveTopology(geometry, 0.01) so the
           endpoint works before the task has run.

        2. **SQL-level JSON aggregation**: the entire GeoJSON FeatureCollection
           is built inside PostgreSQL using ``json_agg`` + ``json_build_object``
           + ``ST_AsGeoJSON``.  This eliminates:
             - 3 000+ ``json.loads()`` calls in Python
             - a Python-level dict-building loop
             - double JSON serialisation (string → dict → string)

        3. **Low-level cache** (``django.core.cache``): keyed as
           ``choropleth:v1``, TTL 30 min.  The key is predictable, so the
           ``build_choropleth_cache`` management command can bust it reliably
           (unlike ``cache_page`` whose keys are request-URL hashes).

        Returns a bare GeoJSON FeatureCollection (no DRF pagination wrapper).
        """
        from django.core.cache import cache
        from django.db import connection

        CACHE_KEY = "choropleth:v1"
        CACHE_TTL = 60 * 30  # 30 minutes

        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return JsonResponse(cached, safe=False)

        sql = """
            SELECT json_build_object(
                'type',     'FeatureCollection',
                'count',    COUNT(*),
                'features', COALESCE(
                    json_agg(
                        json_build_object(
                            'type',     'Feature',
                            'id',       c.fips_code,
                            'geometry', CASE
                                WHEN c.simplified_geometry IS NOT NULL
                                    THEN ST_AsGeoJSON(c.simplified_geometry, 6)::json
                                ELSE ST_AsGeoJSON(
                                        ST_SimplifyPreserveTopology(c.geometry, 0.01),
                                        6
                                     )::json
                            END,
                            'properties', json_build_object(
                                'fips_code',         c.fips_code,
                                'name',              c.name,
                                'state_abbreviation', s.abbreviation,
                                'loss_area_ha',      latest.loss_area_ha,
                                'loss_year',         latest.year
                            )
                        )
                    ),
                    '[]'::json
                )
            )
            FROM geodata_county c
            JOIN geodata_state s ON s.id = c.state_id
            LEFT JOIN LATERAL (
                SELECT loss_area_ha, year
                FROM deforestation_treecoverloss
                WHERE county_id = c.id
                ORDER BY year DESC
                LIMIT 1
            ) latest ON true
        """

        with connection.cursor() as cursor:
            cursor.execute(sql)
            (payload,) = cursor.fetchone()

        cache.set(CACHE_KEY, payload, CACHE_TTL)
        # payload is already a dict (Django's psycopg2 driver deserialises json columns)
        return JsonResponse(payload, safe=False)
