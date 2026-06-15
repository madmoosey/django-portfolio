"""
ArborWatch — Celery Application Configuration.

Initializes the Celery app, autodiscovers tasks from all installed apps,
and configures queue routing for task segregation.
"""

import os

from celery import Celery
from celery.signals import setup_logging

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("arborwatch")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# namespace='CELERY' means all celery-related configuration keys
# should have a `CELERY_` prefix in Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

from celery.schedules import crontab

app.conf.beat_schedule = {
    "ingest-tree-cover-loss-weekly": {
        "task": "apps.ingest.tasks.deforestation_tasks.ingest_tree_cover_loss",
        "schedule": crontab(day_of_week="sun", hour=2, minute=0),
    },
    "ingest-weather-daily": {
        "task": "apps.ingest.tasks.weather_tasks.ingest_temperature_observations",
        "schedule": crontab(hour=4, minute=0),
    },
    "ingest-active-alerts-15m": {
        "task": "apps.ingest.tasks.storm_tasks.ingest_active_alerts",
        "schedule": crontab(minute="*/15"),
    },
    "build-feature-matrix-weekly": {
        "task": "apps.ingest.tasks.analysis_tasks.build_feature_matrix",
        "schedule": crontab(day_of_week="sun", hour=4, minute=0),
    },
    "predict-risk-scores-weekly": {
        "task": "apps.ingest.tasks.analysis_tasks.predict_county_risk_scores",
        "schedule": crontab(day_of_week="sun", hour=6, minute=0),
    },
}


@setup_logging.connect
def config_loggers(*args, **kwargs):
    """Use Django's logging configuration for Celery workers."""
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for verifying Celery connectivity."""
    print(f"Request: {self.request!r}")
