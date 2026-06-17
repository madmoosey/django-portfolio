from django_filters import rest_framework as filters

from .models import DeforestationAlert, TreeCoverLoss


class TreeCoverLossFilter(filters.FilterSet):
    year__gte = filters.NumberFilter(field_name="year", lookup_expr="gte")
    year__lte = filters.NumberFilter(field_name="year", lookup_expr="lte")
    county = filters.CharFilter(field_name="county__fips_code")
    state = filters.CharFilter(field_name="county__state__abbreviation")

    class Meta:
        model = TreeCoverLoss
        fields = ["year", "county", "state", "data_source"]


class DeforestationAlertFilter(filters.FilterSet):
    date__gte = filters.DateFilter(field_name="alert_date", lookup_expr="gte")
    date__lte = filters.DateFilter(field_name="alert_date", lookup_expr="lte")
    county = filters.CharFilter(field_name="county__fips_code")
    state = filters.CharFilter(field_name="county__state__abbreviation")

    class Meta:
        model = DeforestationAlert
        fields = ["alert_type", "confidence", "county", "state"]
