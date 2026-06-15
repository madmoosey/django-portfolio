import abc

import numpy as np
import pandas as pd
import xgboost as xgb


class RiskPredictor(abc.ABC):
    """Abstract base class for ML risk predictors."""

    def __init__(self, model_version=None):
        self.model_version = model_version
        self.model = None

    @abc.abstractmethod
    def train(self, X_train, y_train):
        """Train the model on feature matrix X and labels y."""
        pass

    @abc.abstractmethod
    def predict(self, X):
        """Generate predictions for feature matrix X."""
        pass

    @abc.abstractmethod
    def evaluate(self, X_test, y_test):
        """Evaluate model performance."""
        pass
