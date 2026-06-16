"""
Tests for apps.api.exceptions and apps.api.permissions.
Covers the two 0% files quickly to push overall coverage above 50%.
"""

from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import NotFound, ValidationError

from apps.api.exceptions import custom_exception_handler
from apps.api.permissions import CanTriggerRecompute, IsAdminOrReadOnly

User = get_user_model()


class TestApiExceptionHandler(TestCase):
    """apps.api.exceptions.custom_exception_handler wraps errors in error envelope."""

    def _context(self):
        return {"view": MagicMock(), "request": MagicMock()}

    def test_returns_none_for_non_drf_exception(self):
        result = custom_exception_handler(ValueError("nope"), self._context())
        self.assertIsNone(result)

    def test_wraps_drf_exception_in_error_key(self):
        exc = NotFound()
        response = custom_exception_handler(exc, self._context())
        self.assertIsNotNone(response)
        self.assertIn("error", response.data)
        self.assertIn("code", response.data["error"])
        self.assertIn("details", response.data["error"])


class TestIsAdminOrReadOnly(TestCase):
    """IsAdminOrReadOnly allows safe methods for anyone, writes only for staff."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsAdminOrReadOnly()

    def _make_request(self, method, user=None):
        request = getattr(self.factory, method.lower())("/")
        request.user = user or MagicMock(is_staff=False, is_authenticated=False)
        return request

    def test_get_is_permitted_for_anonymous(self):
        request = self._make_request("GET")
        self.assertTrue(self.permission.has_permission(request, None))

    def test_post_is_denied_for_non_staff(self):
        user = MagicMock(is_staff=False)
        request = self._make_request("POST", user=user)
        self.assertFalse(self.permission.has_permission(request, None))

    def test_post_is_allowed_for_staff(self):
        user = MagicMock(is_staff=True)
        request = self._make_request("POST", user=user)
        self.assertTrue(self.permission.has_permission(request, None))


class TestCanTriggerRecompute(TestCase):
    """CanTriggerRecompute allows only superusers."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = CanTriggerRecompute()

    def test_superuser_is_allowed(self):
        request = self.factory.post("/")
        request.user = MagicMock(is_superuser=True)
        self.assertTrue(self.permission.has_permission(request, None))

    def test_regular_user_is_denied(self):
        request = self.factory.post("/")
        request.user = MagicMock(is_superuser=False)
        self.assertFalse(self.permission.has_permission(request, None))
