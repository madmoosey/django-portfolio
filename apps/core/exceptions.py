"""
ArborWatch Core — Custom Exception Handler.

Provides a consistent error response format across the entire API.
All errors follow the structure:
    {
        "error": {
            "code": "error_code",
            "message": "Human-readable message",
            "details": { ... }  # Optional field-level errors
        }
    }
"""

import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.

    Wraps all error responses in a consistent envelope format.
    Logs server errors (5xx) at ERROR level for monitoring.
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_code = getattr(exc, "default_code", "error")
        error_message = str(exc.detail) if hasattr(exc, "detail") else str(exc)

        # Build structured error response
        error_body = {
            "error": {
                "code": error_code,
                "message": error_message,
                "status_code": response.status_code,
            }
        }

        # Include field-level validation errors
        if isinstance(exc.detail, dict):
            error_body["error"]["details"] = exc.detail
            error_body["error"]["message"] = "Validation failed."
        elif isinstance(exc.detail, list):
            error_body["error"]["details"] = exc.detail
            error_body["error"]["message"] = "Multiple errors occurred."

        response.data = error_body

        # Log 5xx errors
        if response.status_code >= 500:
            logger.error(
                "Server error [%s]: %s — View: %s",
                response.status_code,
                error_message,
                context.get("view", "unknown"),
                exc_info=True,
            )

    return response


class ServiceUnavailableError(APIException):
    """Raised when an external service (GFW, NOAA, etc.) is unreachable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "An external service is temporarily unavailable. Please try again later."
    default_code = "service_unavailable"


class DataIngestionError(APIException):
    """Raised when a data ingestion task encounters an unrecoverable error."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Data ingestion failed. The operations team has been notified."
    default_code = "ingestion_error"


class RateLimitExceededError(APIException):
    """Raised when an external API rate limit is hit."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "External API rate limit exceeded. Task will be retried."
    default_code = "rate_limit_exceeded"
