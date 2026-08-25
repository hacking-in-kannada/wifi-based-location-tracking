"""
Outlier detection and removal for CSI.
Identifies outlier values along the packet time series (axis=0) and replaces them
with the median of the corresponding subcarrier.
"""

import numpy as np


def remove_outliers(x: np.ndarray, method: str = "zscore", threshold: float = 3.0) -> np.ndarray:
    """
    Detects outliers along the time axis (axis=0) and replaces them with subcarrier medians.
    
    Args:
        x: Array of shape (n_packets, n_subcarriers)
        method: Method to use, either "zscore" or "iqr"
        threshold: The threshold above which a point is considered an outlier.
                   For "zscore", standard is 3.0. For "iqr", standard is 1.5.
                   
    Returns:
        cleaned_x: Cleaned array of same shape
    """
    if x.shape[0] <= 2:
        return x.copy()

    # Operates on real numbers (like amplitude or unwrapped phase)
    # If complex, clean real and imaginary parts independently
    if np.iscomplexobj(x):
        real_cleaned = remove_outliers(x.real, method=method, threshold=threshold)
        imag_cleaned = remove_outliers(x.imag, method=method, threshold=threshold)
        return real_cleaned + 1j * imag_cleaned

    cleaned = x.copy()
    medians = np.median(x, axis=0)

    if method == "zscore":
        mean = np.mean(x, axis=0)
        std = np.std(x, axis=0)
        eps = 1e-8
        z_scores = np.abs((x - mean) / (std + eps))
        outliers = z_scores > threshold

    elif method == "iqr":
        q25 = np.percentile(x, 25, axis=0)
        q75 = np.percentile(x, 75, axis=0)
        iqr = q75 - q25
        lower_bound = q25 - threshold * iqr
        upper_bound = q75 + threshold * iqr
        outliers = (x < lower_bound) | (x > upper_bound)

    else:
        raise ValueError(f"Unknown outlier removal method: {method}. Choose 'zscore' or 'iqr'.")

    # Replace outliers with median values of the respective subcarrier column
    for col in range(x.shape[1]):
        col_outliers = outliers[:, col]
        cleaned[col_outliers, col] = medians[col]

    return cleaned
