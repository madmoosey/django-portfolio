import logging

from django.db import transaction
from django.utils import timezone

from celery import shared_task

from apps.analysis.services import AnalysisService

logger = logging.getLogger(__name__)

# All risk types the inference pipeline supports.
RISK_TYPES = ["heat_wave", "hurricane", "tornado"]


# ---------------------------------------------------------------------------
# Task 1 – Feature matrix build
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3)
def build_feature_matrix(self, date_ref=None):
    """
    Weekly Celery task to extract features for all counties and persist them
    as FeatureSnapshot records.

    Args:
        date_ref (str | None): ISO date string ('YYYY-MM-DD') to build
            features for.  Defaults to today.  Pass an explicit value to
            trigger a historical backfill.

    Returns:
        dict: {'date_ref': str, 'success': bool}

    Scheduled every Sunday at 04:00 UTC (see config/celery.py).
    predict_county_risk_scores runs at 06:00 UTC and depends on this
    task completing first.
    """
    if date_ref is None:
        date_ref_obj = timezone.now().date()
    else:
        from datetime import date as _date

        date_ref_obj = _date.fromisoformat(date_ref)

    logger.info(f"Starting feature matrix build for date_ref={date_ref_obj}.")

    service = AnalysisService()

    try:
        success = service.build_features(date_ref=date_ref_obj)
    except Exception as exc:
        logger.error(
            f"Feature matrix build failed for {date_ref_obj}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=300)  # retry after 5 min

    if success:
        logger.info(f"Feature matrix build completed successfully for {date_ref_obj}.")
    else:
        logger.warning(f"Feature matrix build returned False for {date_ref_obj}.")

    return {"date_ref": str(date_ref_obj), "success": bool(success)}


# ---------------------------------------------------------------------------
# Task 2 – Batch risk score inference
# ---------------------------------------------------------------------------


@shared_task(bind=True, max_retries=3)
def predict_county_risk_scores(self, date_ref=None, risk_types=None):
    """
    Weekly Celery task to run inference for all counties using the active
    champion model for each risk type, then persist CountyRiskScore records.

    Each risk type is run independently so a missing/broken model for one
    type does not abort the others.

    Args:
        date_ref (str | None): ISO date string ('YYYY-MM-DD') for the
            reference date.  Defaults to today.
        risk_types (list[str] | None): Subset of risk types to infer.
            Defaults to all three: ['heat_wave', 'hurricane', 'tornado'].

    Returns:
        dict: Mapping of risk_type → {'success': bool, 'error': str | None}

    Scheduled every Sunday at 06:00 UTC (see config/celery.py), two hours
    after build_feature_matrix so snapshots are ready.
    """
    if date_ref is None:
        date_ref_obj = timezone.now().date()
    else:
        from datetime import date as _date

        date_ref_obj = _date.fromisoformat(date_ref)

    targets = risk_types if risk_types else RISK_TYPES

    logger.info(
        f"Starting batch risk prediction for risk_types={targets}, " f"date_ref={date_ref_obj}."
    )

    service = AnalysisService()
    results = {}
    any_success = False

    for risk_type in targets:
        logger.info(f"Running inference: risk_type={risk_type}.")
        try:
            success = service.run_inference(risk_type=risk_type, date_ref=date_ref_obj)
            results[risk_type] = {"success": bool(success), "error": None}
            if success:
                any_success = True
                logger.info(f"Inference completed: risk_type={risk_type}.")
            else:
                logger.warning(
                    f"Inference returned False for risk_type={risk_type}. "
                    "Likely no active model or no feature snapshots."
                )
        except Exception as exc:
            logger.error(
                f"Inference raised an exception for risk_type={risk_type}: {exc}",
                exc_info=True,
            )
            results[risk_type] = {"success": False, "error": str(exc)}

    failed = [rt for rt, r in results.items() if not r["success"]]
    if failed:
        logger.warning(f"Inference failed or skipped for risk_types={failed}.")

    # Retry the whole task only if *every* risk type failed, which indicates a
    # systemic issue (e.g. DB unreachable, no feature snapshots at all).
    if not any_success and targets:
        logger.error(
            "All risk type inferences failed — scheduling retry.",
            extra={"results": results},
        )
        raise self.retry(countdown=600)  # retry after 10 min

    logger.info(
        f"Batch risk prediction finished: "
        f"{len(targets) - len(failed)}/{len(targets)} risk types succeeded."
    )
    return results
