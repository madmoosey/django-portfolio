"""
ArborWatch — Local Development Settings.

DEBUG enabled, console email, django-debug-toolbar, relaxed security.
Usage: DJANGO_SETTINGS_MODULE=config.settings.local
"""

from .base import *  # noqa: F401, F403

# =============================================================================
# CORE
# =============================================================================

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# =============================================================================
# INSTALLED APPS (Dev Extras — only if installed)
# =============================================================================

try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE = [  # noqa: F405
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ] + MIDDLEWARE  # noqa: F405
except ImportError:
    pass

try:
    import django_extensions  # noqa: F401

    INSTALLED_APPS += ["django_extensions"]  # noqa: F405
except ImportError:
    pass

# =============================================================================
# DEBUG TOOLBAR
# =============================================================================

INTERNAL_IPS = ["127.0.0.1", "0.0.0.0"]

# Docker-specific: allow debug toolbar when behind Docker network
import socket

hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS += [".".join(ip.split(".")[:-1] + ["1"]) for ip in ips]

# =============================================================================
# EMAIL (Console backend for dev)
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =============================================================================
# CELERY (Eager execution for easier debugging)
# =============================================================================

# Uncomment to run tasks synchronously during development:
# CELERY_TASK_ALWAYS_EAGER = True
# CELERY_TASK_EAGER_PROPAGATES = True

# =============================================================================
# LOGGING (More verbose for dev)
# =============================================================================

LOGGING["loggers"]["apps"]["level"] = "DEBUG"  # noqa: F405
LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "WARNING",  # Set to DEBUG to see SQL queries
    "propagate": False,
}
