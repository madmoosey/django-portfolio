from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class APITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.admin = User.objects.create_superuser(username="admin", password="password123")

    def test_health_check_endpoint(self):
        """Test health check returns 200"""
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)

    def test_pagination_default(self):
        """Test that list endpoints return paginated data."""
        response = self.client.get("/api/v1/geodata/states/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)

    def test_admin_permissions(self):
        """Test that read-only access is permitted but write requires admin (using standard viewsets)."""
        response = self.client.post("/api/v1/geodata/states/", data={"name": "Test"})
        # Should be 401 Unauthorized for anonymous
        self.assertEqual(response.status_code, 401)

        # Test with standard user
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/v1/geodata/states/", data={"name": "Test"})
        # Should be 403 Forbidden for standard user since they aren't admin (assuming IsAdminOrReadOnly)
        self.assertIn(response.status_code, [403, 405])  # 405 if viewset is ReadOnlyModelViewSet
