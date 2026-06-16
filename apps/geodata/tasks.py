"""
Geodata Celery tasks.

build_choropleth_geometry
    Pre-computes County.simplified_geometry via a single bulk SQL UPDATE and
    busts the choropleth API response cache.

    Trigger conditions:
    - Automatically after every weekly deforestation ingest (via beat schedule)
    - On-demand: call build_choropleth_geometry.delay() from anywhere
    - Manually from Django admin (Celery Results → Periodic Tasks)

    No management command is needed — the task is environment-portable and
    works identically in local Docker, staging, and production.
"""

import logging
import time

from django.core.cache import cache
from django.db import connection

from celery import shared_task

logger = logging.getLogger(__name__)

# Must match the key used in the choropleth viewset action
CHOROPLETH_CACHE_KEY = "choropleth:v1"


@shared_task(bind=True, max_retries=2, name="apps.geodata.tasks.build_choropleth_geometry")
def build_choropleth_geometry(self, tolerance: float = 0.01, force: bool = False):
    """
    Pre-compute County.simplified_geometry using a single bulk SQL UPDATE
    (ST_SimplifyPreserveTopology) and bust the choropleth response cache.

    Args:
        tolerance: Simplification tolerance in degrees (default 0.01 ≈ 1 km).
        force:     If True, re-computes all counties even if already populated.

    Returns:
        dict: {'updated': N, 'elapsed_s': float}

    Performance note: the UPDATE touches all ~3 100 county rows in one SQL
    statement — typically completes in 10-30 s on a standard Postgres instance.
    The choropleth endpoint then uses the stored geometry instead of calling
    ST_SimplifyPreserveTopology on every request, saving ~80 % of query time.
    """
    where_clause = "" if force else "WHERE simplified_geometry IS NULL"

    logger.info("build_choropleth_geometry starting " f"(tolerance={tolerance}°, force={force})")

    t0 = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE geodata_county
                SET    simplified_geometry = ST_SimplifyPreserveTopology(geometry, %s)
                {where_clause}
                """,
                [tolerance],
            )
            updated = cursor.rowcount
    except Exception as exc:
        logger.error(f"build_choropleth_geometry DB error: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)

    elapsed = time.perf_counter() - t0

    # Bust the response cache so the next choropleth request returns fresh data
    cache.delete(CHOROPLETH_CACHE_KEY)
    logger.info(
        f"build_choropleth_geometry complete: "
        f"{updated} rows updated in {elapsed:.1f}s. Cache busted."
    )

    return {"updated": updated, "elapsed_s": round(elapsed, 2)}
