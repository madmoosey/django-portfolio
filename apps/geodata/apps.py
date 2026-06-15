"""ArborWatch Geodata App Configuration."""

from django.apps import AppConfig


class GeodataConfig(AppConfig):
    """Geodata application configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.geodata"
    label = "geodata"
    verbose_name = "Geographic Data"
