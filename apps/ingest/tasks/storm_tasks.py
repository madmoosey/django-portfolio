import logging

from celery import shared_task

from apps.ingest.clients.noaa_client import NOAAClient
from apps.storms.models import ActiveAlert

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def ingest_active_alerts(self):
    """
    Celery task to ingest active severe weather alerts from NWS.
    Runs every 15 minutes.
    """
    client = NOAAClient()
    logger.info("Fetching active weather alerts from NWS.")

    data = client.get_active_alerts()
    if not data or "features" not in data:
        logger.warning("No features returned from NWS API")
        return 0

    success_count = 0
    # Process alerts and save to database (implementation placeholder)
    # We would parse the JSON-LD payload into ActiveAlert objects

    logger.info(f"Successfully processed {success_count} alerts.")
    return success_count


@shared_task
def ingest_storm_events():
    """
    Download and parse NOAA Storm Events DB CSV.
    """
    logger.info("Starting NOAA Storm Events ingestion.")
    # Implementation placeholder
    return True
