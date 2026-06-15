import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

from .base import RiskPredictor


class HurricanePredictor(RiskPredictor):
    """XGBoost Classifier for predicting Hurricane impacts."""

    def __init__(self, model_version=None):
        super().__init__(model_version)
        self.model = xgb.XGBClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=5,
            objective="binary:logistic",
            eval_metric="auc",
            use_label_encoder=False,
        )

    def train(self, X_train, y_train):
        self.model.fit(X_train, y_train)

    def predict(self, X):
        return self.model.predict_proba(X)[:, 1]

    def evaluate(self, X_test, y_test):
        preds = self.model.predict(X_test)
        probs = self.predict(X_test)
        return {
            "accuracy": accuracy_score(y_test, preds),
            "precision": precision_score(y_test, preds, zero_division=0),
            "recall": recall_score(y_test, preds, zero_division=0),
            "auc": roc_auc_score(y_test, probs),
        }
