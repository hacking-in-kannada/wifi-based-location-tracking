"""
K-Nearest Neighbors (KNN) Localization Model.
Conforms to the LocalizationModel interface.
"""

from typing import Dict, Tuple
import numpy as np
from sklearn.neighbors import KNeighborsClassifier

from localization.base import LocalizationModel


class KNNLocalizer(LocalizationModel):
    """
    Distance-weighted K-Nearest Neighbors classifier for CSI room zone classification.
    """

    def __init__(self, n_neighbors: int = 5):
        self.n_neighbors = n_neighbors
        self.clf = KNeighborsClassifier(n_neighbors=n_neighbors, weights="distance")
        self.classes_ = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "KNNLocalizer":
        n_samples = len(X)
        # Dynamically bound neighbors by available samples to prevent sklearn ValueError
        self.clf.n_neighbors = min(self.n_neighbors, n_samples)
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
