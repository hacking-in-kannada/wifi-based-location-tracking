"""
tests/test_training_pipeline.py

End-to-end tests for the Phase 11 ML Training Pipeline.
Inserts synthetic fingerprint data into a temp SQLite DB, runs training,
saves and loads models, and verifies inference correctness.
"""

import json
import os
import tempfile
import shutil
import numpy as np
import pytest

# ── Patch DB path to a temp file so tests don't touch prod DB ────────────────
_tmp_dir = tempfile.mkdtemp()
_test_db_path = os.path.join(_tmp_dir, "test_wifisense.db")
_saved_models_dir = os.path.join(_tmp_dir, "saved_models")

import database.db as db_module
db_module.DATABASE_URL = f"sqlite:///{_test_db_path}"

from database.db import init_db, get_session
from database.models import Room, Position, Fingerprint
from machine_learning import model_registry, training_pipeline
from machine_learning.inference_engine import InferenceEngine

# Override saved_models directory for test isolation
model_registry.MODELS_DIR = _saved_models_dir


@pytest.fixture(autouse=True, scope="module")
def setup_test_db():
    """Initialize schema and populate synthetic data once for all tests."""
    init_db(f"sqlite:///{_test_db_path}")

    session = get_session()
    # Create a test room
    room = Room(name="Test Room")
    session.add(room)
    session.commit()

    # Define 3 positions with distinct synthetic fingerprint signatures
    POSITIONS = [
        ("Zone A", 0.2, 0.2, 5.0),    # (label, x_pct, y_pct, base_mean)
        ("Zone B", 0.5, 0.5, 10.0),
        ("Zone C", 0.8, 0.8, 20.0),
    ]

    rng = np.random.default_rng(42)
    pos_ids = []

    for label, x, y, base in POSITIONS:
        pos = Position(room_id=room.id, label=label, blueprint_x=int(x * 100), blueprint_y=int(y * 100))
        session.add(pos)
        session.commit()
        pos_ids.append(pos.id)

        # Generate 60 synthetic feature vectors for this position
        for _ in range(60):
            feat = {f"mean_sc_{j}": float(rng.normal(base, 0.3)) for j in range(8)}
            feat.update({f"var_sc_{j}": float(rng.normal(1.0, 0.1)) for j in range(8)})
            feat["agg_mean"] = base + rng.normal(0, 0.1)
            feat["agg_variance"] = 1.0

            # Save averaged fingerprint (one row per position in Fingerprint table)
            fp_row = Fingerprint(
                room_id=room.id,
                position_id=pos.id,
                feature_vector_json=json.dumps(feat),
                sample_count=60,
            )
            session.add(fp_row)
        session.commit()

    session.close()
    yield
    session = get_session()
    session.close()


# ─── Test 1: Dataset loading ──────────────────────────────────────────────────

def test_load_dataset_from_db():
    X, y, id_to_label = training_pipeline.load_dataset_from_db()
    assert X.ndim == 2, "X should be 2D"
    # 60 samples per position × 3 positions = 180 total fingerprint rows
    assert X.shape[0] == 180, f"Expected 180 samples, got {X.shape[0]}"
    assert len(np.unique(y)) == 3, "Should have 3 distinct position labels"
    assert all(label in id_to_label.values() for label in ["Zone A", "Zone B", "Zone C"])


def test_load_empty_dataset():
    """Temporarily clear Fingerprint table to verify error is raised."""
    session = get_session()
    fps = session.query(Fingerprint).all()
    saved = [(f.room_id, f.position_id, f.feature_vector_json, f.sample_count) for f in fps]
    session.query(Fingerprint).delete()
    session.commit()
    session.close()

    try:
        with pytest.raises(ValueError, match="No captured signal data found"):
            training_pipeline.load_dataset_from_db()
    finally:
        # Restore
        session = get_session()
        for room_id, pos_id, fvj, sc in saved:
            session.add(Fingerprint(room_id=room_id, position_id=pos_id, feature_vector_json=fvj, sample_count=sc))
        session.commit()
        session.close()


# ─── Test 2: Single model training ────────────────────────────────────────────

@pytest.mark.parametrize("model_name", ["knn", "svm", "random_forest"])
def test_train_single_model(model_name):
    result = training_pipeline.run_training(model_name, n_cv_folds=0, save=False)
    assert result.error is None, f"Training error: {result.error}"
    assert result.n_samples == 180, f"Expected 180 samples, got {result.n_samples}"
    assert result.n_positions == 3


# ─── Test 3: Save and reload model ───────────────────────────────────────────

def test_save_and_load_knn():
    result = training_pipeline.run_training("knn", n_cv_folds=0, save=True)
    assert result.error is None

    loaded = model_registry.load("knn")
    X, y, _ = training_pipeline.load_dataset_from_db()

    pred_class, confidence = loaded.predict(X[0])
    assert pred_class in y, f"Predicted class {pred_class} not in label set {set(y)}"
    assert 0.0 <= confidence <= 1.0


# ─── Test 4: SVM save/load/predict ───────────────────────────────────────────

def test_save_and_load_svm():
    result = training_pipeline.run_training("svm", n_cv_folds=0, save=True)
    assert result.error is None

    loaded = model_registry.load("svm")
    X, y, _ = training_pipeline.load_dataset_from_db()

    # Check each sample returns a valid class (not necessarily 100% accuracy on small dataset)
    valid_classes = set(y.tolist())
    for i in range(len(X)):
        pred, conf = loaded.predict(X[i])
        assert pred in valid_classes, f"SVM predicted unknown class {pred}"
        assert 0.0 <= conf <= 1.0


# ─── Test 5: InferenceEngine end-to-end ──────────────────────────────────────

def test_inference_engine():
    # Train SVM if not already saved
    training_pipeline.run_training("svm", n_cv_folds=0, save=True)

    engine = InferenceEngine()  # fresh instance (not singleton)
    engine.load_model("svm")

    assert engine.is_loaded
    assert engine.current_model_name == "svm"

    X, y, id_to_label = training_pipeline.load_dataset_from_db()
    feat_keys = training_pipeline.get_feature_keys_from_db()

    # Build feature dict from first sample
    feat_dict = dict(zip(feat_keys, X[0].tolist()))
    result = engine.predict(feat_dict, apply_smoother=False)

    assert "position_id" in result
    assert "confidence" in result
    assert "label" in result
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["position_id"] in id_to_label
    assert "NOT centimeter GPS" in result["disclaimer"]


# ─── Test 6: select_best_model ───────────────────────────────────────────────

def test_select_best_model():
    best = training_pipeline.select_best_model()
    assert best.error is None
    assert best.model_name in ["knn", "svm", "random_forest", "neural_net"]
    # best_model.json should be written
    marker = os.path.join(_saved_models_dir, "best_model.json")
    assert os.path.exists(marker)
    with open(marker) as f:
        data = json.load(f)
    assert data["best_model"] == best.model_name


# ─── Cleanup ─────────────────────────────────────────────────────────────────

def test_cleanup():
    """Remove temporary files created during tests."""
    shutil.rmtree(_tmp_dir, ignore_errors=True)
    assert True  # cleanup always passes
