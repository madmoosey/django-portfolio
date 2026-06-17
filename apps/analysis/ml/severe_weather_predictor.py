"""
Severe Weather risk predictor — Phase 1 (rule-based) and Phase 2 (XGBoost).

Phase 1: heuristic from alert frequency, severity, recency.
Phase 2: XGBoost trained on FeatureSnapshot history, labelled by whether the
county had an Extreme/Severe NWS alert in the 7 days following each snapshot.
"""

import logging

import pandas as pd
import xgboost as xgb

from .base import RiskPredictor

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "sw_alert_count",
    "sw_extreme_count",
    "sw_days_since_last",
    "sw_has_tornado",
    "sw_has_flood",
    "sw_has_thunderstorm",
]

CONF_RULE_BASED = 35.0
CONF_XGBOOST = 68.0


class SevereWeatherPredictor(RiskPredictor):
    """
    Dual-phase predictor for county-level severe weather risk.

    Usage:
        predictor = SevereWeatherPredictor()
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
        logger.info(f"SevereWeatherPredictor trained on {len(y_train)} samples.")

    def predict(self, X: pd.DataFrame):
        return self.model.predict_proba(X)[:, 1]

    def evaluate(self, X_test: pd.DataFrame, y_test):
        from sklearn.metrics import roc_auc_score

        probs = self.predict(X_test)
        return {"auc": roc_auc_score(y_test, probs) if len(set(y_test)) > 1 else 0.5}

    # ── Rule-based scorer (Phase 1) ──────────────────────────────────────────

    @staticmethod
    def rule_based_score(features: dict) -> tuple:
        extreme = float(features.get("sw_extreme_count", 0))
        count = float(features.get("sw_alert_count", 0))
        days_ago = float(features.get("sw_days_since_last", 90))
        has_torn = float(features.get("sw_has_tornado", 0))

        recency_score = max(0.0, (90 - days_ago) / 90) * 20
        freq_score = min(count / 30, 1.0) * 30
        extreme_score = min(extreme / 10, 1.0) * 40
        tornado_bonus = has_torn * 10  # tornados are highly impactful

        score = round(min(recency_score + freq_score + extreme_score + tornado_bonus, 100.0), 2)
        factors = {
            "recency": round(recency_score, 2),
            "frequency": round(freq_score, 2),
            "extreme_events": round(extreme_score, 2),
            "tornado_factor": round(tornado_bonus, 2),
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
