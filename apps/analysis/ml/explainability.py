import pandas as pd
import shap


class ModelExplainer:
    """Generates SHAP feature importance for a given prediction."""

    def __init__(self, model):
        # TreeExplainer is heavily optimized for XGBoost
        self.explainer = shap.TreeExplainer(model)

    def explain_prediction(self, X):
        """
        Returns a dictionary of feature names to their SHAP values for a single prediction.
        X should be a 1D array or single-row DataFrame.
        """
        shap_values = self.explainer.shap_values(X)

        if isinstance(X, pd.DataFrame):
            feature_names = X.columns
        else:
            feature_names = [f"feature_{i}" for i in range(len(shap_values[0]))]

        # For binary classification, shap_values is sometimes a list of arrays
        # (one per class). For XGBoost binary logistic, it's typically a single array.
        if isinstance(shap_values, list):
            vals = shap_values[1][0]  # SHAP for positive class
        else:
            vals = shap_values[0]

        explanation = {str(name): float(val) for name, val in zip(feature_names, vals)}

        # Sort by absolute impact
        explanation = dict(sorted(explanation.items(), key=lambda item: abs(item[1]), reverse=True))
        return explanation
