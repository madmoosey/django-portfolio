from rest_framework.pagination import CursorPagination, PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for most endpoints."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


class TimeSeriesCursorPagination(CursorPagination):
    """Cursor pagination optimized for time-series data like observations/alerts."""

    page_size = 100
    ordering = "-created_at"  # Needs to be overridden per viewset if timestamp field differs
