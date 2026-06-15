"""
ArborWatch Core Models.

Provides:
    - BaseModel: Abstract model with audit fields for all ArborWatch models.
    - User: Custom user model extending AbstractUser for future extensibility.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model providing audit fields for all ArborWatch models.

    Fields:
        id: UUID primary key (avoids sequential ID exposure in APIs).
        created_at: Auto-set on creation.
        updated_at: Auto-set on every save.
        is_active: Soft-delete flag. Prefer filtering over hard deletes.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this record.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this record was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last updated.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Soft-delete flag. Inactive records are excluded from default querysets.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        """Mark this record as inactive instead of deleting it."""
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_active = True
        self.save(update_fields=["is_active", "updated_at"])


class ActiveManager(models.Manager):
    """Manager that returns only active (non-soft-deleted) records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class User(AbstractUser):
    """
    Custom user model for ArborWatch.

    Extends Django's AbstractUser to allow future customization
    (e.g., API key management, organization membership, notification prefs).
    Must be defined before the first migration is created.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.get_full_name() or self.username
