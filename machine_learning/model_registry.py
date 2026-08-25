"""
machine_learning/model_registry.py

Central registry for saving and loading all WiFiSense localization model types.
Supports joblib serialization for sklearn models (KNN, SVM, Random Forest)
and torch.save / torch.load for the PyTorch MLP.
"""

import json
import os
import datetime
from typing import Optional, Dict, Any

import joblib
import numpy as np

from localization.base import LocalizationModel
from localization.knn import KNNLocalizer
from localization.svm import SVMLocalizer
from localization.random_forest import RandomForestLocalizer
from localization.neural_net import NeuralNetLocalizer, PyTorchMLP


# Directory where trained model files are persisted
MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")

# Mapping from model name string to (class, file extension)
MODEL_CONFIG: Dict[str, Dict] = {
    "knn":          {"cls": KNNLocalizer,          "ext": "joblib"},
    "svm":          {"cls": SVMLocalizer,          "ext": "joblib"},
    "random_forest":{"cls": RandomForestLocalizer, "ext": "joblib"},
    "neural_net":   {"cls": NeuralNetLocalizer,    "ext": "pt"},
}


def _ensure_dir() -> None:
    os.makedirs(MODELS_DIR, exist_ok=True)


def _model_path(name: str) -> str:
    ext = MODEL_CONFIG[name]["ext"]
    return os.path.join(MODELS_DIR, f"{name}.{ext}")


def _meta_path(name: str) -> str:
    return os.path.join(MODELS_DIR, f"{name}_meta.json")


def save(name: str, model: LocalizationModel, metadata: Dict[str, Any]) -> str:
    """
    Persists a trained model to disk.

    Args:
        name: Model key, one of "knn", "svm", "random_forest", "neural_net"
        model: Fitted LocalizationModel instance
        metadata: Dict of training metrics to save alongside the model

    Returns:
        path: Absolute path to the saved model file
    """
    if name not in MODEL_CONFIG:
        raise ValueError(f"Unknown model name: {name!r}. Valid: {list(MODEL_CONFIG)}")

    _ensure_dir()
    path = _model_path(name)
    ext = MODEL_CONFIG[name]["ext"]

    if ext == "joblib":
        joblib.dump(model, path)
    elif ext == "pt":
        import torch
        # Save the complete NeuralNetLocalizer (state + class mappings)
        torch.save({
            "state_dict": model.model.state_dict(),
            "classes_": model.classes_.tolist(),
            "id_to_idx": model._id_to_idx,
            "idx_to_id": model._idx_to_id,
            "input_dim": model.input_dim,
            "epochs": model.epochs,
            "lr": model.lr,
            "batch_size": model.batch_size,
        }, path)

    # Write metadata JSON
    metadata["saved_at"] = datetime.datetime.utcnow().isoformat()
    metadata["model_name"] = name
    metadata["model_path"] = path
    with open(_meta_path(name), "w") as f:
        json.dump(metadata, f, indent=2)

    return path


def load(name: str) -> LocalizationModel:
    """
    Loads a previously saved model from disk.

    Args:
        name: Model key, one of "knn", "svm", "random_forest", "neural_net"

    Returns:
        model: Ready-to-predict LocalizationModel instance

    Raises:
        FileNotFoundError: If the model file doesn't exist.
    """
    if name not in MODEL_CONFIG:
        raise ValueError(f"Unknown model name: {name!r}. Valid: {list(MODEL_CONFIG)}")

    path = _model_path(name)
    ext = MODEL_CONFIG[name]["ext"]

    if not os.path.exists(path):
        raise FileNotFoundError(f"No saved model found at {path!r}. Train first.")

    if ext == "joblib":
        return joblib.load(path)

    elif ext == "pt":
        import torch
        checkpoint = torch.load(path, weights_only=False)
        classes_ = np.array(checkpoint["classes_"])
        input_dim = checkpoint["input_dim"]
        num_classes = len(classes_)

        # Rebuild PyTorchMLP and restore weights
        net = PyTorchMLP(input_dim, num_classes)
        net.load_state_dict(checkpoint["state_dict"])
        net.eval()

        # Reconstruct NeuralNetLocalizer wrapper
        model = NeuralNetLocalizer(
            epochs=checkpoint["epochs"],
            lr=checkpoint["lr"],
            batch_size=checkpoint["batch_size"],
        )
        model.model = net
        model.classes_ = classes_
        model.input_dim = input_dim
        model._id_to_idx = {int(k): v for k, v in checkpoint["id_to_idx"].items()}
        model._idx_to_id = {int(k): v for k, v in checkpoint["idx_to_id"].items()}
        return model

    raise RuntimeError(f"Unhandled extension: {ext}")


def load_metadata(name: str) -> Optional[Dict[str, Any]]:
    """Returns the training metadata dict for a saved model, or None if not found."""
    path = _meta_path(name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_saved() -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Returns a dict of {model_name -> metadata_or_None} for all model types,
    indicating which ones have been trained and saved.
    """
    result = {}
    for name in MODEL_CONFIG:
        result[name] = load_metadata(name)
    return result


def instantiate(name: str) -> LocalizationModel:
    """Creates a fresh (untrained) model instance by name."""
    if name not in MODEL_CONFIG:
        raise ValueError(f"Unknown model name: {name!r}")
    return MODEL_CONFIG[name]["cls"]()
