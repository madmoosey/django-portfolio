import logging
import time
import uuid

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """
    Middleware to assign a unique correlation ID to each request
    and log the request duration.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Assign correlation ID
        request_id = str(uuid.uuid4())
        request.correlation_id = request_id

        start_time = time.time()

        response = self.get_response(request)

        duration = time.time() - start_time

        # Log basic request data
        if request.path.startswith("/api/"):
            logger.info(
                f"API Request [ID: {request_id}] - {request.method} {request.path} - "
                f"Status: {response.status_code} - Duration: {duration:.3f}s"
            )

        # Add correlation ID to response headers
        response["X-Correlation-ID"] = request_id

        return response
