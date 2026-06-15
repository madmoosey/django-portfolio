from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class TieredAnonRateThrottle(AnonRateThrottle):
    """Anonymous users get a basic rate limit (100/hour)."""

    rate = "100/hour"


class TieredUserRateThrottle(UserRateThrottle):
    """Authenticated users get a higher rate limit (1000/hour)."""

    rate = "1000/hour"


class AdminBypassThrottle(UserRateThrottle):
    """Admins bypass throttling entirely."""

    def allow_request(self, request, view):
        if request.user and request.user.is_staff:
            return True
        return super().allow_request(request, view)
