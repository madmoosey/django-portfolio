"""
ArborWatch Core Views.

Health check endpoint for load balancer and monitoring.
"""

import logging
import time

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views import View
from redis import Redis

logger = logging.getLogger(__name__)


class HealthCheckView(View):
    """
    Health check endpoint for load balancers and container orchestration.

    Returns 200 with component status if all services are healthy.
    Returns 503 if any critical service is unreachable.

    Response format:
        {
            "status": "healthy" | "unhealthy",
            "version": "1.0.0",
            "checks": {
                "database": {"status": "up", "latency_ms": 1.2},
                "redis": {"status": "up", "latency_ms": 0.5},
            }
        }
    """

    def get(self, request, *args, **kwargs):
        checks = {}
        all_healthy = True

        # Check database
        checks["database"] = self._check_database()
        if checks["database"]["status"] != "up":
            all_healthy = False

        # Check Redis
        checks["redis"] = self._check_redis()
        if checks["redis"]["status"] != "up":
            all_healthy = False

        response_data = {
            "status": "healthy" if all_healthy else "unhealthy",
            "version": settings.SPECTACULAR_SETTINGS.get("VERSION", "unknown"),
            "checks": checks,
        }

        status_code = 200 if all_healthy else 503
        return JsonResponse(response_data, status=status_code)

    def _check_database(self):
        """Verify database connectivity and measure latency."""
        try:
            start = time.monotonic()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            return {"status": "up", "latency_ms": latency_ms}
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return {"status": "down", "error": str(e)}

    def _check_redis(self):
        """Verify Redis connectivity and measure latency."""
        try:
            redis_url = settings.CACHES.get("default", {}).get("LOCATION", "")
            if not redis_url:
                return {"status": "unknown", "error": "Redis not configured"}

            start = time.monotonic()
            client = Redis.from_url(redis_url, socket_connect_timeout=2)
            client.ping()
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            client.close()
            return {"status": "up", "latency_ms": latency_ms}
        except Exception as e:
            logger.error("Redis health check failed: %s", e)
            return {"status": "down", "error": str(e)}
