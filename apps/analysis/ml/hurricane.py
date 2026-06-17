"""Hurricane risk predictor — Phase 1 (rule-based) and Phase 2 (XGBoost)."""

import logging

import pandas as pd
import xgboost as xgb

from .base import RiskPredictor

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "hur_historical_count",
    "hur_recent_count",
    "hur_deaths",
    "hur_alert_count",
    "hur_extreme_alert_count",
    "hur_days_since_last_alert",
    "hur_coastal_proximity",
]

CONF_RULE_BASED = 38.0
CONF_XGBOOST = 70.0


class HurricanePredictor(RiskPredictor):
    """Prospective Increased Possibility of Hurricane predictor."""

    def __init__(self, model_version=None):
        super().__init__(model_version)
        self.model = xgb.XGBClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=5,
            objective="binary:logistic",
            eval_metric="auc",
            verbosity=0,
        )
        self._trained = False

    def train(self, X_train: pd.DataFrame, y_train):
        self.model.fit(X_train, y_train, verbose=False)
        self._trained = True
        logger.info(f"HurricanePredictor trained on {len(y_train)} samples.")

    def predict(self, X: pd.DataFrame):
        return self.model.predict_proba(X)[:, 1]

    def evaluate(self, X_test, y_test):
        from sklearn.metrics import roc_auc_score

        probs = self.predict(X_test)
        return {"auc": roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.5}

    @staticmethod
    def rule_based_score(features: dict) -> tuple:
        hist = float(features.get("hur_historical_count", 0))
        recent = float(features.get("hur_recent_count", 0))
        deaths = float(features.get("hur_deaths", 0))
        alerts = float(features.get("hur_extreme_alert_count", 0))
        days = float(features.get("hur_days_since_last_alert", 90))
        coast = float(features.get("hur_coastal_proximity", 0))

        hist_score = min(hist / 50, 1.0) * 25
        recent_score = min(recent / 5, 1.0) * 30
        severity_score = min(deaths / 100, 1.0) * 15
        alert_score = min(alerts / 5, 1.0) * 20
        recency_score = max(0.0, (90 - days) / 90) * 5
        coast_bonus = coast * 5

        score = round(
            min(
                hist_score
                + recent_score
                + severity_score
                + alert_score
                + recency_score
                + coast_bonus,
                100.0,
            ),
            2,
        )
        return score, {
            "historical": round(hist_score, 2),
            "recent_activity": round(recent_score, 2),
            "severity": round(severity_score, 2),
            "active_alerts": round(alert_score, 2),
            "coastal": round(coast_bonus, 2),
        }

    def score_county(self, features: dict) -> tuple:
        if self._trained:
            X = pd.DataFrame([{c: float(features.get(c, 0)) for c in FEATURE_COLS}])
            prob = float(self.predict(X)[0])
            score = round(prob * 100, 2)
            return (
                score,
                CONF_XGBOOST,
                {c: round(float(features.get(c, 0)), 4) for c in FEATURE_COLS},
            )
        score, factors = self.rule_based_score(features)
        return score, CONF_RULE_BASED, factors
