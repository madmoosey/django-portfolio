import logging
from datetime import datetime

import pandas as pd

from django.utils import timezone

from apps.geodata.models import County

from .features.pipeline import FeaturePipeline
from .ml.explainability import ModelExplainer
from .ml.registry import ModelRegistry
from .models import CountyRiskScore, FeatureSnapshot

logger = logging.getLogger(__name__)


class AnalysisService:
    """Orchestrates feature extraction, inference, and persistence."""

    def __init__(self):
        self.registry = ModelRegistry()
        # In a real implementation, extractors would be instantiated here
        self.pipeline = FeaturePipeline(extractors=[])

    def build_features(self, date_ref=None):
        """Build and persist feature matrix for all counties."""
        date_ref = date_ref or timezone.now().date()
        logger.info(f"Building feature matrix for {date_ref}")

        matrix = self.pipeline.build_matrix(date_ref)
        counties = {c.fips_code: c for c in County.objects.all()}

        # Persist snapshots
        for fips, features in matrix.items():
            FeatureSnapshot.objects.update_or_create(
                county=counties[fips], snapshot_date=date_ref, defaults={"features": features}
            )
        return True

    def run_inference(self, risk_type, date_ref=None):
        """Run inference using the champion model for a specific risk type."""
        date_ref = date_ref or timezone.now().date()

        model, model_record = self.registry.load_active_model(risk_type)
        if not model:
            logger.error(f"No active model found for risk_type={risk_type}")
            return False

        explainer = ModelExplainer(model)

        # Fetch latest feature snapshots
        snapshots = FeatureSnapshot.objects.filter(snapshot_date=date_ref)
        if not snapshots.exists():
            logger.warning(f"No feature snapshots found for {date_ref}. Cannot run inference.")
            return False

        for snapshot in snapshots:
            # Convert feature dict to 1-row DataFrame for XGBoost
            if not snapshot.features:
                continue

            X = pd.DataFrame([snapshot.features])

            try:
                # Predict probability
                prob = model.predict_proba(X)[0][1]
                score = round(prob * 100, 2)

                # Get SHAP explanations
                shap_factors = explainer.explain_prediction(X)

                CountyRiskScore.objects.update_or_create(
                    county=snapshot.county,
                    risk_type=risk_type,
                    computed_at=timezone.now(),
                    defaults={
                        "score": score,
                        "confidence": 95.0,  # Placeholder for actual model confidence bounds
                        "factors": shap_factors,
                        "data_window_start": date_ref.replace(year=date_ref.year - 1),
                        "data_window_end": date_ref,
                    },
                )
            except Exception as e:
                logger.error(f"Inference failed for county {snapshot.county.fips_code}: {e}")

        logger.info(f"Inference completed for {risk_type}")
        return True
