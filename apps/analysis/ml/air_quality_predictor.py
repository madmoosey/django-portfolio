"""
Air Quality risk predictor — Phase 1 (rule-based) and Phase 2 (XGBoost).

Phase 1: rule-based score from raw feature values. Runs immediately with any
amount of data. Confidence = 40 (clearly "speculative").

Phase 2: XGBoost binary classifier trained inline on FeatureSnapshot history,
labelled by whether the county had AQI > 100 in the 7 days following the
snapshot date. Activates automatically once the task has accumulated 30 days
of daily snapshots. Confidence = 72.
"""

import logging

import pandas as pd
import xgboost as xgb

from .base import RiskPredictor

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "aq_obs_count",
    "aq_max_aqi",
    "aq_mean_aqi",
    "aq_unhealthy_days",
    "aq_pm25_fraction",
]

# AQI threshold that constitutes a "bad air" event for labelling
BAD_AIR_AQI = 100

# Confidence values by phase
CONF_RULE_BASED = 40.0
CONF_XGBOOST = 72.0


class AirQualityPredictor(RiskPredictor):
    """
    Dual-phase predictor for county-level air quality risk.

    Usage:
        predictor = AirQualityPredictor()
        # optional: predictor.train(X_df, y_list)
        score, conf, factors = predictor.score_county(feature_dict)
    """

    def __init__(self, model_version=None):
        super().__init__(model_version)
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=4,
            objective="binary:logistic",
            eval_metric="auc",
            verbosity=0,
        )
        self._trained = False

    # ── XGBoost interface (Phase 2) ──────────────────────────────────────────

    def train(self, X_train: pd.DataFrame, y_train):
        self.model.fit(X_train, y_train, verbose=False)
        self._trained = True
        logger.info(f"AirQualityPredictor trained on {len(y_train)} samples.")

    def predict(self, X: pd.DataFrame):
        return self.model.predict_proba(X)[:, 1]

    def evaluate(self, X_test: pd.DataFrame, y_test):
        from sklearn.metrics import roc_auc_score

        probs = self.predict(X_test)
        return {"auc": roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.5}

    # ── Rule-based scorer (Phase 1) ──────────────────────────────────────────

    @staticmethod
    def rule_based_score(features: dict) -> tuple:
        """Heuristic 0–100 score + factor breakdown."""
        unhealthy_days = float(features.get("aq_unhealthy_days", 0))
        max_aqi = float(features.get("aq_max_aqi", 0))
        pm25_frac = float(features.get("aq_pm25_fraction", 0))

        freq_score = min(unhealthy_days / 30, 1.0) * 60
        severity_score = min(max_aqi / 500, 1.0) * 25
        pm25_score = pm25_frac * 15

        score = round(min(freq_score + severity_score + pm25_score, 100.0), 2)
        factors = {
            "frequency": round(freq_score, 2),
            "severity": round(severity_score, 2),
            "pm25_weight": round(pm25_score, 2),
        }
        return score, factors

    # ── Unified entry point ───────────────────────────────────────────────────

    def score_county(self, features: dict) -> tuple:
        """
        Returns (score: float 0-100, confidence: float 0-100, factors: dict).
        Auto-dispatches to XGBoost if trained, otherwise rule-based.
        """
        if self._trained:
            X = pd.DataFrame([{c: float(features.get(c, 0)) for c in FEATURE_COLS}])
            prob = float(self.predict(X)[0])
            score = round(prob * 100, 2)
            factors = {c: round(float(features.get(c, 0)), 4) for c in FEATURE_COLS}
            return score, CONF_XGBOOST, factors
        else:
            score, factors = self.rule_based_score(features)
            return score, CONF_RULE_BASED, factors
