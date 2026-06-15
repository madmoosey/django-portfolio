"""
ArborWatch Geodata Filters.

Allows filtering states and counties by attributes and spatial bounding boxes.
"""

import django_filters
from rest_framework_gis.filters import InBBoxFilter

from apps.geodata.models import County, State


class StateFilter(django_filters.FilterSet):
    """Filters for the State viewset."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    abbreviation = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = State
        fields = ["fips_code", "name", "abbreviation"]


class CountyFilter(django_filters.FilterSet):
    """Filters for the County viewset."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    state_abbreviation = django_filters.CharFilter(
        field_name="state__abbreviation", lookup_expr="iexact"
    )

    class Meta:
        model = County
        fields = ["fips_code", "name", "state", "state_abbreviation"]
