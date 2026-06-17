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

# Explicitly include every task submodule so workers import them before starting.
# This is more reliable than relying on autodiscover_tasks() + __init__.py wildcard
# imports — a missing line in __init__.py would cause NotRegistered errors at runtime.
app.conf.include = [
    "apps.geodata.tasks",
    "apps.ingest.tasks.air_quality_tasks",
    "apps.ingest.tasks.analysis_tasks",
    "apps.ingest.tasks.deforestation_tasks",
    "apps.ingest.tasks.storm_tasks",
    "apps.ingest.tasks.weather_tasks",
]

# Also run autodiscover for any other apps that define tasks.py at the top level.
app.autodiscover_tasks()

from celery.schedules import crontab

app.conf.beat_schedule = {
    "ingest-tree-cover-loss-weekly": {
        "task": "apps.ingest.tasks.deforestation_tasks.ingest_tree_cover_loss",
        "schedule": crontab(day_of_week="sun", hour=2, minute=0),
    },
    "sync-weather-stations-monthly": {
        "task": "apps.ingest.tasks.weather_tasks.sync_weather_stations",
        # 1st of every month at 01:00 UTC — runs before the daily 04:00 ingest
        # so any new stations are present when observations are collected.
        "schedule": crontab(day_of_month=1, hour=1, minute=0),
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
    "ingest-air-quality-hourly": {
        "task": "apps.ingest.tasks.air_quality_tasks.ingest_air_quality_observations",
        # AirNow publishes new hourly data ~10 min after the hour; run at :15
        # to ensure fresh readings are always available.
        "schedule": crontab(minute=15),
    },
    # Run 1 hour after the Sunday deforestation ingest (02:00) so simplified
    # geometries are always in sync with fresh loss data.
    "build-choropleth-geometry-weekly": {
        "task": "apps.geodata.tasks.build_choropleth_geometry",
        "schedule": crontab(day_of_week="sun", hour=3, minute=0),
    },
    # Environmental ML risk predictions — daily so the map layer stays fresh.
    # Phase 1 (rule-based) starts immediately; Phase 2 (XGBoost) activates
    # automatically after 30 days of accumulated FeatureSnapshot history.
    "predict-environmental-risks-daily": {
        "task": "apps.ingest.tasks.analysis_tasks.predict_environmental_risks",
        "schedule": crontab(hour=6, minute=30),
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
