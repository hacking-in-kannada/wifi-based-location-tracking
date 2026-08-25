"""
machine_learning/training_pipeline.py

Core training pipeline for WiFiSense localization models.
Loads fingerprints from the SQLite database, builds feature matrix X and label
vector y, runs optional cross-validation, selects the best model, and saves to
the model registry.

Accuracy note:
    All models classify the closest matching trained zone/location.
    Predictions are NOT centimeter-level GPS coordinates.
    Every result carries a confidence score.
"""

import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Callable

import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler
import joblib
import os

from database.db import get_session
from database.models import Position, Fingerprint, FingerprintSample
from localization.base import LocalizationModel
from machine_learning import model_registry


# ─── Data Types ─────────────────────────────────────────────────────────────

@dataclass
class TrainingResult:
    """Outcome of a single model training run."""
    model_name: str
    accuracy: float          # mean CV accuracy in [0, 1]
    f1: float                # mean CV macro F1 in [0, 1]
    latency_ms: float        # mean per-sample inference time in ms
    n_samples: int
    n_positions: int
    feature_dim: int
    saved_path: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Dataset Loading ─────────────────────────────────────────────────────────

def load_dataset_from_db() -> Tuple[np.ndarray, np.ndarray, Dict[int, str]]:
    """
    Reads FingerprintSample (or fallback Fingerprint) rows from the database
    and builds feature matrix X and label array y.

    Returns:
        X: ndarray of shape (n_samples, n_features)
        y: ndarray of shape (n_samples,) — integer position IDs
        id_to_label: dict mapping position_id → human-readable label

    Raises:
        ValueError: If fewer than 2 positions have fingerprints/samples.
    """
    session = get_session()
    try:
        samples = session.query(FingerprintSample).all()
        rows = []
        labels = []

        if samples and len(set(s.position_id for s in samples)) >= 2:
            for s in samples:
                feat_dict = json.loads(s.feature_vector_json)
                keys = sorted(feat_dict.keys())
                vec = [feat_dict[k] for k in keys]
                rows.append(vec)
                labels.append(s.position_id)
        else:
            fingerprints = session.query(Fingerprint).all()
            if not fingerprints:
                raise ValueError("No captured signal data found in database. Please select a position and click 'START 10S CAPTURE' first.")

            for fp in fingerprints:
                feat_dict = json.loads(fp.feature_vector_json)
                keys = sorted(feat_dict.keys())
                vec = [feat_dict[k] for k in keys]
                rows.append(vec)
                labels.append(fp.position_id)

        positions = session.query(Position).all()
        id_to_label: Dict[int, str] = {p.id: p.label for p in positions}

        unique_labels = set(labels)
        if len(unique_labels) < 2:
            raise ValueError(
                f"Training requires fingerprints from at least 2 distinct room locations. Currently found {len(unique_labels)} location with captured data. Please select a second location and click 'START 10S CAPTURE'."
            )

        X = np.array(rows, dtype=np.float64)
        y = np.array(labels, dtype=np.int64)
        return X, y, id_to_label
    finally:
        session.close()


def get_feature_keys_from_db() -> List[str]:
    """Returns the sorted list of feature keys from the first fingerprint row."""
    session = get_session()
    try:
        fp = session.query(Fingerprint).first()
        if fp is None:
            return []
        return sorted(json.loads(fp.feature_vector_json).keys())
    finally:
        session.close()


# ─── Training ────────────────────────────────────────────────────────────────

def run_training(
    model_name: str,
    n_cv_folds: int = 5,
    save: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> TrainingResult:
    """
    Trains a single model on the database fingerprints and optionally saves it.

    Args:
        model_name: One of "knn", "svm", "random_forest", "neural_net"
        n_cv_folds: K for StratifiedKFold cross-validation (0 to skip CV)
        save: Whether to persist the final model to disk
        progress_cb: Optional callback(message: str) for streaming progress logs

    Returns:
        TrainingResult dataclass with metrics and saved path
    """
    def log(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    log(f"[PIPELINE] Loading fingerprints from database...")
    try:
        X, y, id_to_label = load_dataset_from_db()
    except ValueError as e:
        return TrainingResult(
            model_name=model_name, accuracy=0.0, f1=0.0, latency_ms=0.0,
            n_samples=0, n_positions=0, feature_dim=0, saved_path="", error=str(e)
        )

    n_samples, feature_dim = X.shape
    n_positions = len(np.unique(y))
    log(f"[PIPELINE] Dataset: {n_samples} samples, {n_positions} positions, {feature_dim} features")

    # Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    accuracies = []
    f1_scores = []
    latencies = []

    if n_cv_folds >= 2 and n_samples >= n_cv_folds * n_positions:
        log(f"[PIPELINE] Running {n_cv_folds}-fold cross-validation for {model_name}...")
        skf = StratifiedKFold(n_splits=n_cv_folds, shuffle=True, random_state=42)
        for fold_i, (train_idx, test_idx) in enumerate(skf.split(X_scaled, y)):
            X_tr, X_te = X_scaled[train_idx], X_scaled[test_idx]
            y_tr, y_te = y[train_idx], y[test_idx]
            m = model_registry.instantiate(model_name)
            m.fit(X_tr, y_tr)
            preds, fold_latencies = [], []
            for sample in X_te:
                t0 = time.perf_counter()
                pred_class, _ = m.predict(sample)
                t1 = time.perf_counter()
                preds.append(pred_class)
                fold_latencies.append((t1 - t0) * 1000)
            acc = accuracy_score(y_te, preds)
            f1 = f1_score(y_te, preds, average="macro", zero_division=0)
            lat = float(np.mean(fold_latencies))
            accuracies.append(acc)
            f1_scores.append(f1)
            latencies.append(lat)
            log(f"[PIPELINE] Fold {fold_i + 1}/{n_cv_folds}: acc={acc:.4f}, F1={f1:.4f}, lat={lat:.2f}ms")
    else:
        log(f"[PIPELINE] Skipping CV (insufficient samples for {n_cv_folds} folds). Training on full set.")

    # Train final model on ALL data
    log(f"[PIPELINE] Training final {model_name} model on full dataset...")
    final_model = model_registry.instantiate(model_name)
    final_model.fit(X_scaled, y)

    # Measure latency on a sample
    t0 = time.perf_counter()
    final_model.predict(X_scaled[0])
    latency_ms = (time.perf_counter() - t0) * 1000

    mean_accuracy = float(np.mean(accuracies)) if accuracies else 0.0
    mean_f1 = float(np.mean(f1_scores)) if f1_scores else 0.0
    mean_latency = float(np.mean(latencies)) if latencies else latency_ms

    # Save scaler alongside model metadata
    saved_path = ""
    if save:
        scaler_path = os.path.join(model_registry.MODELS_DIR, f"{model_name}_scaler.joblib")
        os.makedirs(model_registry.MODELS_DIR, exist_ok=True)
        joblib.dump(scaler, scaler_path)

        metadata = {
            "accuracy": mean_accuracy,
            "f1": mean_f1,
            "latency_ms": mean_latency,
            "n_samples": n_samples,
            "n_positions": n_positions,
            "feature_dim": feature_dim,
            "feature_keys": get_feature_keys_from_db(),
            "id_to_label": {str(k): v for k, v in id_to_label.items()},
            "scaler_path": scaler_path,
        }
        saved_path = model_registry.save(model_name, final_model, metadata)
        log(f"[PIPELINE] Model saved to {saved_path}")

    log(
        f"[PIPELINE] Done. {model_name}: accuracy={mean_accuracy:.4f}, "
        f"F1={mean_f1:.4f}, latency={mean_latency:.2f}ms"
    )

    return TrainingResult(
        model_name=model_name,
        accuracy=mean_accuracy,
        f1=mean_f1,
        latency_ms=mean_latency,
        n_samples=n_samples,
        n_positions=n_positions,
        feature_dim=feature_dim,
        saved_path=saved_path,
    )


def select_best_model(
    progress_cb: Optional[Callable[[str], None]] = None,
) -> TrainingResult:
    """
    Trains all 4 model types with cross-validation, picks the highest accuracy,
    saves the winner, and returns its TrainingResult.
    """
    def log(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    log("[PIPELINE] Auto-selection: training all 4 models...")
    candidates = ["knn", "svm", "random_forest", "neural_net"]
    results: Dict[str, TrainingResult] = {}

    for name in candidates:
        log(f"[PIPELINE] --- Training {name} ---")
        result = run_training(name, n_cv_folds=5, save=True, progress_cb=progress_cb)
        results[name] = result

    # Pick best by CV accuracy (skip any that errored)
    valid = {k: v for k, v in results.items() if v.error is None}
    if not valid:
        first_err = list(results.values())[0]
        return first_err

    best_name = max(valid, key=lambda k: valid[k].accuracy)
    best = valid[best_name]
    log(
        f"[PIPELINE] Best model: {best_name} "
        f"(accuracy={best.accuracy:.4f}, F1={best.f1:.4f})"
    )

    # Write a "best_model" marker so InferenceEngine knows which to load by default
    marker_path = os.path.join(model_registry.MODELS_DIR, "best_model.json")
    with open(marker_path, "w") as f:
        json.dump({"best_model": best_name, **best.to_dict()}, f, indent=2)

    return best
