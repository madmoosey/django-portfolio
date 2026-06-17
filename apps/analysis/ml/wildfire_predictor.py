"""Wildfire risk predictor — Phase 1 (rule-based) and Phase 2 (XGBoost)."""

import logging

import pandas as pd
import xgboost as xgb

from .base import RiskPredictor

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "wf_historical_count",
    "wf_recent_count",
    "wf_alert_count",
    "wf_extreme_alert_count",
    "wf_days_since_last_alert",
    "wf_pm25_max_aqi",
    "wf_pm25_smoke_days",
    "wf_western_proximity",
    "wf_season_factor",
]

CONF_RULE_BASED = 38.0
CONF_XGBOOST = 70.0


class WildfirePredictor(RiskPredictor):
    """Prospective Increased Possibility of Wildfire predictor."""

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
        logger.info(f"WildfirePredictor trained on {len(y_train)} samples.")

    def predict(self, X: pd.DataFrame):
        return self.model.predict_proba(X)[:, 1]

    def evaluate(self, X_test, y_test):
        from sklearn.metrics import roc_auc_score

        probs = self.predict(X_test)
        return {"auc": roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.5}

    @staticmethod
    def rule_based_score(features: dict) -> tuple:
        hist = float(features.get("wf_historical_count", 0))
        recent = float(features.get("wf_recent_count", 0))
        alerts = float(features.get("wf_extreme_alert_count", 0))
        days = float(features.get("wf_days_since_last_alert", 90))
        pm25_max = float(features.get("wf_pm25_max_aqi", 0))
        smoke_days = float(features.get("wf_pm25_smoke_days", 0))
        western = float(features.get("wf_western_proximity", 0))
        season = float(features.get("wf_season_factor", 0))

        hist_score = min(hist / 30, 1.0) * 20
        recent_score = min(recent / 5, 1.0) * 20
        alert_score = min(alerts / 3, 1.0) * 15
        recency = max(0.0, (90 - days) / 90) * 5
        smoke_score = min(pm25_max / 500, 1.0) * 15 + min(smoke_days / 10, 1.0) * 10
        geo_bonus = western * 10
        season_bonus = season * 5

        score = round(
            min(
                hist_score
                + recent_score
                + alert_score
                + recency
                + smoke_score
                + geo_bonus
                + season_bonus,
                100.0,
            ),
            2,
        )
        return score, {
            "historical": round(hist_score, 2),
            "recent_activity": round(recent_score, 2),
            "fire_weather_alerts": round(alert_score, 2),
            "pm25_smoke_proxy": round(smoke_score, 2),
            "western_us": round(geo_bonus, 2),
            "fire_season": round(season_bonus, 2),
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
