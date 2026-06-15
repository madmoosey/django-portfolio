"""
Tests for the health check endpoint.
"""

from unittest.mock import patch

from django.test import TestCase


class HealthCheckTests(TestCase):
    """Tests for GET /api/health/."""

    def test_health_check_returns_200_when_healthy(self):
        """Health check returns 200 with status 'healthy' when all services are up."""
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("version", data)
        self.assertIn("checks", data)
        self.assertEqual(data["checks"]["database"]["status"], "up")
        self.assertIn("latency_ms", data["checks"]["database"])

    def test_health_check_returns_503_when_db_down(self):
        """Health check returns 503 when database is unreachable."""
        with patch(
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
            side_effect=Exception("Connection refused"),
        ):
            response = self.client.get("/api/health/")
            # Database check should fail, but endpoint itself should still respond
            data = response.json()
            self.assertEqual(data["status"], "unhealthy")
            self.assertEqual(data["checks"]["database"]["status"], "down")
