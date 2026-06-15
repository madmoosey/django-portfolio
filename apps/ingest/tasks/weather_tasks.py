import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.db import transaction
from apps.weather.models import WeatherStation, TemperatureObservation
from apps.ingest.clients.noaa_client import NOAAClient

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def ingest_temperature_observations(self):
    """
    Celery task to ingest yesterday's temperature data for all active stations.
    """
    client = NOAAClient()
    stations = WeatherStation.objects.filter(is_active=True)

    # Ingest for yesterday
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info(
        f"Starting temperature ingestion for {stations.count()} stations for date {yesterday}."
    )

    success_count = 0

    for station in stations:
        try:
            data = client.get_daily_summaries(station.station_id, yesterday, yesterday)
            if data:
                with transaction.atomic():
                    for record in data:
                        tmax = record.get("TMAX")
                        tmin = record.get("TMIN")
                        prcp = record.get("PRCP")

                        # Calculate TAVG if both min/max exist
                        tavg = None
                        if tmax is not None and tmin is not None:
                            tavg = (float(tmax) + float(tmin)) / 2.0

                        TemperatureObservation.objects.update_or_create(
                            station=station,
                            date=record.get("DATE"),
                            defaults={
                                "tmax_celsius": tmax,
                                "tmin_celsius": tmin,
                                "tavg_celsius": tavg,
                                "precipitation_mm": prcp,
                            },
                        )
                success_count += 1
        except Exception as e:
            logger.error(f"Failed to ingest data for station {station.station_id}: {e}")

    logger.info(
        f"Successfully ingested temperature data for {success_count}/{stations.count()} stations."
    )
    return success_count


@shared_task
def sync_station_counties():
    """
    Spatially map stations to counties using PostGIS.
    """
    logger.info("Syncing weather stations to counties via spatial join...")
    # Will be implemented using ST_Contains
    return True
