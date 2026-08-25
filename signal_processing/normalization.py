"""
Amplitude normalization utilities for CSI.
Supports per-packet z-score and min-max normalization.
"""

import numpy as np


def amplitude_normalize(amp: np.ndarray, method: str = "zscore") -> np.ndarray:
    """
    Normalizes the CSI amplitude values per-packet (across subcarriers, axis=1).
    
    Args:
        amp: Array of shape (n_packets, n_subcarriers)
        method: Normalization method, either "zscore" or "minmax"
        
    Returns:
        normalized_amp: Normalized array of same shape
    """
    if amp.shape[0] == 0 or amp.shape[1] == 0:
        return amp.copy()

    eps = 1e-8  # Prevent division by zero

    if method == "zscore":
        mean = np.mean(amp, axis=1, keepdims=True)
        std = np.std(amp, axis=1, keepdims=True)
        return (amp - mean) / (std + eps)

    elif method == "minmax":
        min_val = np.min(amp, axis=1, keepdims=True)
        max_val = np.max(amp, axis=1, keepdims=True)
        return (amp - min_val) / (max_val - min_val + eps)

    else:
        raise ValueError(f"Unknown normalization method: {method}. Choose 'zscore' or 'minmax'.")
