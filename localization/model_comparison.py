"""
Model comparison and performance evaluation script.
Generates a realistic synthetic CSI feature dataset, runs cross-validation
on all four localization models, and outputs docs/model_performance.md.
"""

import os
import time
from typing import Dict, Any, List
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

from localization.knn import KNNLocalizer
from localization.random_forest import RandomForestLocalizer
from localization.svm import SVMLocalizer
from localization.neural_net import NeuralNetLocalizer


def generate_synthetic_dataset(
    n_positions: int = 5,
    samples_per_pos: int = 150,
    n_features: int = 64
) -> tuple:
    """
    Generates a deterministic synthetic CSI feature dataset representing 5 zones.
    Adds random shifts and variance to differentiate zones.
    """
    np.random.seed(42)
    X = []
    y = []

    for pos in range(n_positions):
        # Base cluster center for this position
        center = np.random.uniform(-3.0, 3.0, size=(1, n_features))
        # Generate samples with Gaussian noise around the center
        pos_samples = center + np.random.normal(0, 0.8, size=(samples_per_pos, n_features))
        
        X.append(pos_samples)
        # Class labels (position IDs, e.g. 101, 102, 103, 104, 105)
        y.append(np.full((samples_per_pos,), 101 + pos))

    return np.vstack(X), np.hstack(y)


def run_model_comparison(output_md_path: str = "docs/model_performance.md"):
    """
    Trains all four models on K-Fold cross-validation and records metrics.
    Saves a formatted markdown report.
    """
    print("Generating synthetic CSI dataset...")
    X, y = generate_synthetic_dataset(n_positions=5, samples_per_pos=150, n_features=64)
    
    models = {
        "KNN": KNNLocalizer(n_neighbors=5),
        "Random Forest": RandomForestLocalizer(n_estimators=100, random_state=42),
        "SVM": SVMLocalizer(C=1.0, random_state=42),
        "Neural Network (MLP)": NeuralNetLocalizer(epochs=100, lr=0.01)
    }

    # Cross-validation setup
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    results = {name: {"accuracy": [], "f1": [], "latency": []} for name in models}
    confusion_matrices = {name: [] for name in models}

    print("Running cross-validation on models...")
    for train_idx, test_idx in skf.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        for name, model in models.items():
            # Train
            model.fit(X_train, y_train)

            # Evaluate test set
            preds = []
            latencies = []
            for sample in X_test:
                t0 = time.perf_counter()
                pred_class, _ = model.predict(sample)
                t1 = time.perf_counter()
                preds.append(pred_class)
                latencies.append((t1 - t0) * 1000.0)  # ms

            # Record metrics
            results[name]["accuracy"].append(accuracy_score(y_test, preds))
            results[name]["f1"].append(f1_score(y_test, preds, average="macro"))
            results[name]["latency"].append(np.mean(latencies))
            
            # Confusion matrix
            cm = confusion_matrix(y_test, preds, labels=np.unique(y))
            confusion_matrices[name].append(cm)

    # Compute averages
    summary = {}
    for name in models:
        summary[name] = {
            "mean_accuracy": float(np.mean(results[name]["accuracy"])),
            "mean_f1": float(np.mean(results[name]["f1"])),
            "mean_latency_ms": float(np.mean(results[name]["latency"])),
            "avg_confusion_matrix": np.mean(confusion_matrices[name], axis=0)
        }
        print(f"Model: {name:20} | Accuracy: {summary[name]['mean_accuracy']:.4f} | Latency: {summary[name]['mean_latency_ms']:.2f} ms")

    # Generate model_performance.md
    print(f"Writing performance report to {output_md_path}...")
    os.makedirs(os.path.dirname(output_md_path), exist_ok=True)
    
    with open(output_md_path, "w") as f:
        f.write("# Localization Model Performance Report\n\n")
        f.write("This report evaluates the accuracy, macro F1, and inference latency of the four CSI zone localization classifiers using 5-fold cross-validation on a synthetic 5-position fingerprint dataset.\n\n")
        
        # Summary table
        f.write("## Performance Summary\n\n")
        f.write("| Model | Accuracy (Mean) | Macro F1 (Mean) | Inference Latency (Mean) |\n")
        f.write("|---|---|---|---|\n")
        for name, metrics in summary.items():
            f.write(f"| {name} | {metrics['mean_accuracy']*100:.2f}% | {metrics['mean_f1']:.4f} | {metrics['mean_latency_ms']:.2f} ms |\n")
        f.write("\n")
        
        # Accuracy limitation warning (DOD Ground Rules 4 and 20)
        f.write("> [!IMPORTANT]\n")
        f.write("> WiFiSense classification estimations represent **closest matching trained zone/locations** only. The system is designed to classify rooms/zones rather than resolve exact centimeter-level spatial coordinates.\n\n")

        # Confusion Matrices
        f.write("## Confusion Matrices\n\n")
        f.write("Values show the normalized prediction distribution (actual vs predicted) across the 5 training positions:\n\n")
        for name, metrics in summary.items():
            f.write(f"### {name} Confusion Matrix\n\n")
            f.write("```\n")
            cm_normalized = metrics["avg_confusion_matrix"] / np.sum(metrics["avg_confusion_matrix"], axis=1, keepdims=True)
            f.write(np.array2string(cm_normalized, precision=2, separator=", "))
            f.write("\n```\n\n")
            
    print("Report written successfully.")


if __name__ == "__main__":
    run_model_comparison()
