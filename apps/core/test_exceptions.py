"""
Tests for apps.core.exceptions — custom exception handler and exception classes.
Covers: custom_exception_handler, ServiceUnavailableError, DataIngestionError,
        RateLimitExceededError (33 statements → pushes coverage well past 50%).
"""

from unittest.mock import MagicMock

from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotFound, ValidationError

from apps.core.exceptions import (
    DataIngestionError,
    RateLimitExceededError,
    ServiceUnavailableError,
    custom_exception_handler,
)


class TestCustomExceptionHandler(TestCase):
    """custom_exception_handler wraps DRF exceptions in the standard envelope."""

    def _context(self):
        return {"view": "TestView", "request": MagicMock()}

    def test_returns_none_for_non_drf_exception(self):
        """Plain Python exceptions pass through as None (no DRF response)."""
        result = custom_exception_handler(ValueError("boom"), self._context())
        self.assertIsNone(result)

    def test_wraps_not_found_in_error_envelope(self):
        exc = NotFound()
        response = custom_exception_handler(exc, self._context())
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertIn("code", response.data["error"])
        self.assertIn("status_code", response.data["error"])

    def test_wraps_authentication_failed(self):
        exc = AuthenticationFailed()
        response = custom_exception_handler(exc, self._context())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["error"]["code"], "authentication_failed")

    def test_validation_error_dict_sets_details_and_message(self):
        exc = ValidationError({"field": ["This field is required."]})
        response = custom_exception_handler(exc, self._context())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("details", response.data["error"])
        self.assertEqual(response.data["error"]["message"], "Validation failed.")

    def test_validation_error_list_sets_details_and_message(self):
        exc = ValidationError(["error one", "error two"])
        response = custom_exception_handler(exc, self._context())
        self.assertIn("details", response.data["error"])
        self.assertEqual(response.data["error"]["message"], "Multiple errors occurred.")


class TestCustomExceptionClasses(TestCase):
    """All three custom exception classes have the right status codes."""

    def test_service_unavailable_error(self):
        exc = ServiceUnavailableError()
        self.assertEqual(exc.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(exc.default_code, "service_unavailable")

    def test_data_ingestion_error(self):
        exc = DataIngestionError()
        self.assertEqual(exc.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(exc.default_code, "ingestion_error")

    def test_rate_limit_exceeded_error(self):
        exc = RateLimitExceededError()
        self.assertEqual(exc.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(exc.default_code, "rate_limit_exceeded")
