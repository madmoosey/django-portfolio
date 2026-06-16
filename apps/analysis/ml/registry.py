import os
import uuid
from datetime import datetime

import joblib

from django.conf import settings

from apps.analysis.models import MLModel


class ModelRegistry:
    """Handles saving, loading, and promoting ML models."""

    def __init__(self):
        self.storage_dir = os.path.join(settings.BASE_DIR, "models_storage")
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def save_model(self, predictor, risk_type, metrics, hyperparameters):
        """Persist a trained model locally (or S3 in production) and register it."""
        version = f"{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
        filename = f"{risk_type}_{version}.joblib"
        filepath = os.path.join(self.storage_dir, filename)

        # Serialize model
        joblib.dump(predictor.model, filepath)

        # Register in DB
        ml_model = MLModel.objects.create(
            name=f"{risk_type}_predictor",
            version=version,
            risk_type=risk_type,
            is_active=False,
            hyperparameters=hyperparameters,
            metrics=metrics,
            s3_path=filepath,  # Local path for now; S3 URL in production
        )
        return ml_model

    def load_active_model(self, risk_type):
        """Load the active champion model for inference."""
        active_record = MLModel.objects.filter(risk_type=risk_type, is_active=True).first()
        if not active_record or not active_record.s3_path:
            return None, None

        try:
            model = joblib.load(active_record.s3_path)
            return model, active_record
        except Exception:
            return None, None

    def promote_to_active(self, model_id):
        """Set a specific model version as active, deactivating others of the same type."""
        model = MLModel.objects.get(id=model_id)
        MLModel.objects.filter(risk_type=model.risk_type).update(is_active=False)
        model.is_active = True
        model.save()
        return model
