"""
Abstract base class for all localization models in the WiFiSense system.
Ensures consistency across all classifier implementations (KNN, Random Forest, SVM, NN).
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Any
import numpy as np


class LocalizationModel(ABC):
    """
    Interface for WiFiSense Localization models.
    """

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "LocalizationModel":
        """
        Trains the localization model on feature matrix X and labels y.
        
        Args:
            X: 2D array of shape (n_samples, n_features)
            y: 1D array of shape (n_samples,) containing integer position IDs
            
        Returns:
            self: The trained model instance.
        """
        pass

    @abstractmethod
    def predict(self, x: np.ndarray) -> Tuple[int, float]:
        """
        Predicts the closest position ID and its associated confidence.
        
        Args:
            x: 1D feature vector of shape (n_features,) or 2D array of shape (1, n_features)
            
        Returns:
            position_id: The predicted integer position ID.
            confidence: Float value in [0.0, 1.0] representing prediction confidence/probability.
        """
        pass

    @abstractmethod
    def predict_proba(self, x: np.ndarray) -> Dict[int, float]:
        """
        Returns a mapping of position IDs to their predicted probabilities.
        
        Args:
            x: 1D feature vector of shape (n_features,) or 2D array of shape (1, n_features)
            
        Returns:
            probabilities: Dict mapping position_id (int) -> probability (float)
        """
        pass
