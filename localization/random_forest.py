"""
Random Forest Localization Model.
Conforms to the LocalizationModel interface.
"""

from typing import Dict, Tuple
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from localization.base import LocalizationModel


class RandomForestLocalizer(LocalizationModel):
    """
    Random Forest classifier for CSI room zone classification.
    """

    def __init__(self, n_estimators: int = 100, max_depth: int = None, random_state: int = 42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state
        self.clf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state
        )
        self.classes_ = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RandomForestLocalizer":
        self.clf.fit(X, y)
        self.classes_ = self.clf.classes_
        return self

    def predict(self, x: np.ndarray) -> Tuple[int, float]:
        if x.ndim == 1:
            x = x.reshape(1, -1)

        pred_class = int(self.clf.predict(x)[0])
        probs = self.clf.predict_proba(x)[0]
        confidence = float(np.max(probs))

        return pred_class, confidence

    def predict_proba(self, x: np.ndarray) -> Dict[int, float]:
        if x.ndim == 1:
            x = x.reshape(1, -1)

        probs = self.clf.predict_proba(x)[0]
        return {int(cls): float(prob) for cls, prob in zip(self.classes_, probs)}
