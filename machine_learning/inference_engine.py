"""
machine_learning/inference_engine.py

Singleton inference engine for real-time zone prediction.
Loads the best saved model from the registry, applies the matching scaler,
feeds predictions through PredictionSmoother, and returns zone + confidence.

Accuracy note:
    Predictions represent the closest matching trained zone/location — NOT
    centimeter-level GPS coordinates. All results include a confidence score.
"""

import json
import os
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import joblib

from localization.base import LocalizationModel
from localization.smoothing import PredictionSmoother
from machine_learning import model_registry


class InferenceEngine:
    """
    Singleton wrapper for zone prediction at runtime.

    Usage:
        engine = InferenceEngine()
        engine.load_model("svm")            # or "auto" for best saved model
        pred = engine.predict(feature_dict)
    """

    _instance: Optional["InferenceEngine"] = None

    def __init__(self, smoother_window: int = 5):
        self._model: Optional[LocalizationModel] = None
        self._scaler: Optional[Any] = None  # sklearn StandardScaler or None
        self._model_name: Optional[str] = None
        self._id_to_label: Dict[int, str] = {}
        self._feature_keys: List[str] = []
        self._smoother = PredictionSmoother(window_size=smoother_window)

    @classmethod
    def get_instance(cls) -> "InferenceEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Loading ──────────────────────────────────────────────────────────────

    def load_model(self, name: str = "auto") -> None:
        """
        Loads a saved model into memory.

        Args:
            name: Model key ("knn", "svm", "random_forest", "neural_net")
                  or "auto" to load the best model from the last auto-select run.

        Raises:
            FileNotFoundError: If no model has been saved yet.
        """
        if name == "auto":
            name = self._find_best_model_name()

        self._model = model_registry.load(name)
        self._model_name = name

        # Load matching scaler
        scaler_path = os.path.join(
            model_registry.MODELS_DIR, f"{name}_scaler.joblib"
        )
        self._scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None

        # Load metadata for label map and feature key ordering
        meta = model_registry.load_metadata(name)
        if meta:
            self._id_to_label = {int(k): v for k, v in meta.get("id_to_label", {}).items()}
            self._feature_keys = meta.get("feature_keys", [])

        # Reset smoother when model changes
        self._smoother = PredictionSmoother(window_size=self._smoother.window_size)

    def _find_best_model_name(self) -> str:
        """Reads best_model.json marker written by select_best_model()."""
        marker_path = os.path.join(model_registry.MODELS_DIR, "best_model.json")
        if os.path.exists(marker_path):
            with open(marker_path) as f:
                return json.load(f)["best_model"]
        # Fallback: pick first available saved model
        saved = model_registry.list_saved()
        for name, meta in saved.items():
            if meta is not None:
                return name
        raise FileNotFoundError(
            "No trained model found. Run training first via POST /api/v1/train."
        )

    # ── Prediction ────────────────────────────────────────────────────────────

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def current_model_name(self) -> Optional[str]:
        return self._model_name

    def predict(
        self,
        feature_dict: Dict[str, float],
        apply_smoother: bool = True,
    ) -> Dict[str, Any]:
        """
        Predicts zone from a pre-extracted feature dictionary.

        Args:
            feature_dict: Keys must match the feature keys used during training.
            apply_smoother: Whether to apply PredictionSmoother for temporal stability.

        Returns:
            {
                "position_id": int,
                "label": str,
                "confidence": float,        # smoothed confidence in [0, 1]
                "all_probs": {pos_id: prob}, # smoothed per-zone probabilities
                "model_name": str,
                "disclaimer": str,
            }
        """
        if not self.is_loaded:
            raise RuntimeError("No model loaded. Call load_model() first.")

        # Build feature vector in the same key order as during training
        if self._feature_keys:
            vec = np.array(
                [feature_dict.get(k, 0.0) for k in self._feature_keys],
                dtype=np.float64
            )
        else:
            # Fallback: sort keys alphabetically
            keys = sorted(feature_dict.keys())
            vec = np.array([feature_dict[k] for k in keys], dtype=np.float64)

        # Apply scaler
        if self._scaler is not None:
            vec = self._scaler.transform(vec.reshape(1, -1)).flatten()

        # Get raw probabilities from model
        raw_probs = self._model.predict_proba(vec)

        # Apply smoother
        if apply_smoother:
            smoothed_probs = self._smoother.add_prediction(raw_probs)
            pos_id, confidence = self._smoother.get_best_position(smoothed_probs)
        else:
            smoothed_probs = raw_probs
            pos_id = max(raw_probs, key=raw_probs.get)
            confidence = raw_probs[pos_id]

        label = self._id_to_label.get(pos_id, f"Position {pos_id}")

        return {
            "position_id": int(pos_id),
            "label": label,
            "confidence": round(float(confidence), 4),
            "all_probs": {int(k): round(float(v), 4) for k, v in smoothed_probs.items()},
            "model_name": self._model_name,
            "disclaimer": (
                "Closest matching trained zone/location — NOT centimeter GPS coordinates."
            ),
        }

    def predict_from_feature_dict(self, feature_dict: Dict[str, float]) -> Dict[str, Any]:
        """Alias for predict() — used directly from REST API."""
        return self.predict(feature_dict)

    def reset_smoother(self) -> None:
        """Clears the smoother history (call after a model reload)."""
        self._smoother = PredictionSmoother(window_size=self._smoother.window_size)


# Module-level singleton accessor
def get_engine() -> InferenceEngine:
    """Returns the global InferenceEngine singleton."""
    return InferenceEngine.get_instance()
