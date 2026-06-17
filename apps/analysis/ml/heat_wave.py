"""Heat wave risk predictor — Phase 1 (rule-based) and Phase 2 (XGBoost)."""

import logging

import pandas as pd
import xgboost as xgb

from .base import RiskPredictor

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "heat_historical_count",
    "heat_recent_count",
    "heat_deaths",
    "heat_alert_count",
    "heat_extreme_alert_count",
    "heat_days_since_last_alert",
    "heat_southern_proximity",
    "heat_season_factor",
]

CONF_RULE_BASED = 38.0
CONF_XGBOOST = 70.0


class HeatWavePredictor(RiskPredictor):
    """Prospective Increased Possibility of Heat Wave predictor."""

    def __init__(self, model_version=None):
        super().__init__(model_version)
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            objective="binary:logistic",
            eval_metric="auc",
            verbosity=0,
        )
        self._trained = False

    def train(self, X_train: pd.DataFrame, y_train):
        self.model.fit(X_train, y_train, verbose=False)
        self._trained = True
        logger.info(f"HeatWavePredictor trained on {len(y_train)} samples.")

    def predict(self, X: pd.DataFrame):
        return self.model.predict_proba(X)[:, 1]

    def evaluate(self, X_test, y_test):
        from sklearn.metrics import roc_auc_score

        probs = self.predict(X_test)
        return {"auc": roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.5}

    @staticmethod
    def rule_based_score(features: dict) -> tuple:
        hist = float(features.get("heat_historical_count", 0))
        recent = float(features.get("heat_recent_count", 0))
        deaths = float(features.get("heat_deaths", 0))
        alerts = float(features.get("heat_extreme_alert_count", 0))
        days = float(features.get("heat_days_since_last_alert", 90))
        southern = float(features.get("heat_southern_proximity", 0))
        season = float(features.get("heat_season_factor", 0))

        hist_score = min(hist / 50, 1.0) * 20
        recent_score = min(recent / 5, 1.0) * 25
        severity_score = min(deaths / 50, 1.0) * 20
        alert_score = min(alerts / 3, 1.0) * 20
        recency_score = max(0.0, (90 - days) / 90) * 5
        geo_bonus = southern * 5
        season_bonus = season * 5

        score = round(
            min(
                hist_score
                + recent_score
                + severity_score
                + alert_score
                + recency_score
                + geo_bonus
                + season_bonus,
                100.0,
            ),
            2,
        )
        return score, {
            "historical": round(hist_score, 2),
            "recent_activity": round(recent_score, 2),
            "severity": round(severity_score, 2),
            "active_alerts": round(alert_score, 2),
            "sun_belt_factor": round(geo_bonus, 2),
            "season_factor": round(season_bonus, 2),
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
