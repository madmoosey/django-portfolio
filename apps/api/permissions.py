from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """
    The request is authenticated as an admin, or is a read-only request.
    """

    def has_permission(self, request, view):
        return bool(request.method in SAFE_METHODS or request.user and request.user.is_staff)


class CanTriggerRecompute(BasePermission):
    """
    Only admins or specific service accounts can trigger risk recomputation.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)
