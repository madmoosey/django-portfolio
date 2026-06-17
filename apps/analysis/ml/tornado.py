import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

from .base import RiskPredictor


class TornadoPredictor(RiskPredictor):
    """XGBoost Classifier for predicting Tornado events."""

    def __init__(self, model_version=None):
        super().__init__(model_version)
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=6,
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
        return {"auc": roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.5}

    @staticmethod
    def rule_based_score(features: dict) -> tuple:
        hist = float(features.get("tor_historical_count", 0))
        recent = float(features.get("tor_recent_count", 0))
        deaths = float(features.get("tor_deaths", 0))
        ef = float(features.get("tor_max_ef_score", 0))
        alerts = float(features.get("tor_extreme_alert_count", 0))
        days = float(features.get("tor_days_since_last_alert", 90))
        alley = float(features.get("tor_alley_proximity", 0))

        hist_score = min(hist / 100, 1.0) * 25
        recent_score = min(recent / 10, 1.0) * 25
        death_score = min(deaths / 50, 1.0) * 5  # fatalities capped at 50 → 5 pts
        ef_score = (ef / 5.0) * 20  # EF0-EF5 → 0-20
        alert_score = min(alerts / 3, 1.0) * 15
        recency = max(0.0, (90 - days) / 90) * 5
        alley_bonus = alley * 5

        score = round(
            min(
                hist_score
                + recent_score
                + death_score
                + ef_score
                + alert_score
                + recency
                + alley_bonus,
                100.0,
            ),
            2,
        )
        return score, {
            "historical": round(hist_score, 2),
            "recent_activity": round(recent_score, 2),
            "fatalities": round(death_score, 2),
            "ef_rating": round(ef_score, 2),
            "active_alerts": round(alert_score, 2),
            "tornado_alley": round(alley_bonus, 2),
        }
