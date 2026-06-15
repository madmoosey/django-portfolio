"""
ArborWatch — ASGI Configuration.

Exposes the ASGI callable as a module-level variable named ``application``.
Supports async views and WebSocket connections if needed.

For more information on this file, see:
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

application = get_asgi_application()
