import logging

from django.utils import timezone

from celery import shared_task

from apps.analysis.services import AnalysisService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def build_feature_matrix(self):
    """
    Weekly Celery task to extract features for all counties and store as FeatureSnapshots.
    """
    logger.info("Starting feature matrix build task.")
    service = AnalysisService()
    success = service.build_features()
    return success


@shared_task(bind=True, max_retries=3)
def predict_county_risk_scores(self):
    """
    Weekly Celery task to run inference for all counties using champion models.
    """
    logger.info("Starting batch risk prediction task.")
    service = AnalysisService()
    date_ref = timezone.now().date()

    for risk_type in ["heat_wave", "hurricane", "tornado"]:
        service.run_inference(risk_type=risk_type, date_ref=date_ref)

    return True
