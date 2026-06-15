"""
Tests for core models — BaseModel and User.
"""

import uuid

from django.test import TestCase

from apps.core.models import User


class UserModelTests(TestCase):
    """Tests for the custom User model."""

    def test_create_user(self):
        """User can be created with default fields."""
        user = User.objects.create_user(
            username="testuser",
            email="test@arborwatch.net",
            password="testpass123",
        )
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@arborwatch.net")
        self.assertTrue(user.check_password("testpass123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsInstance(user.id, uuid.UUID)

    def test_create_superuser(self):
        """Superuser has all permissions."""
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@arborwatch.net",
            password="adminpass123",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_user_str_with_full_name(self):
        """__str__ returns full name when available."""
        user = User.objects.create_user(
            username="jdoe",
            first_name="John",
            last_name="Doe",
            password="pass123",
        )
        self.assertEqual(str(user), "John Doe")

    def test_user_str_without_full_name(self):
        """__str__ falls back to username when name is empty."""
        user = User.objects.create_user(
            username="anonymous",
            password="pass123",
        )
        self.assertEqual(str(user), "anonymous")

    def test_user_uuid_primary_key(self):
        """User PK is a UUID, not a sequential integer."""
        user = User.objects.create_user(username="uuidtest", password="pass123")
        self.assertIsInstance(user.pk, uuid.UUID)
        # Ensure it's not the nil UUID
        self.assertNotEqual(user.pk, uuid.UUID(int=0))
