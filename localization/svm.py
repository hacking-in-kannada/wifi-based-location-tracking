"""
Support Vector Machine (SVM) Localization Model.
Conforms to the LocalizationModel interface.
"""

from typing import Dict, Tuple
import numpy as np
from sklearn.svm import SVC

from localization.base import LocalizationModel


class SVMLocalizer(LocalizationModel):
    """
    Support Vector Machine classifier for CSI room zone classification.
    Uses probability=True for calibrated confidence estimates.
    """

    def __init__(self, C: float = 1.0, kernel: str = "rbf", random_state: int = 42):
        self.C = C
        self.kernel = kernel
        self.random_state = random_state
        self.clf = SVC(C=C, kernel=kernel, probability=True, random_state=random_state)
        self.classes_ = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "SVMLocalizer":
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
