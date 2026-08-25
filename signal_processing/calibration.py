"""
CSI phase calibration and sanitization.
Removes carrier frequency offsets (CFO) and sampling frequency offsets (SFO) 
by unwrapping raw phase and removing the linear trend across subcarriers.
"""

import numpy as np


def phase_unwrap_and_calibrate(phase_raw: np.ndarray) -> np.ndarray:
    """
    Sanitizes raw CSI phase by unwrapping along the subcarrier axis (axis=1)
    and removing the linear phase ramp using least-squares regression.
    
    Args:
        phase_raw: Array of shape (n_packets, n_subcarriers) containing raw phase values.
        
    Returns:
        calibrated_phase: Array of shape (n_packets, n_subcarriers) with linear trends removed.
    """
    if phase_raw.shape[0] == 0 or phase_raw.shape[1] <= 1:
        return phase_raw.copy()

    n_packets, n_subcarriers = phase_raw.shape

    # 1. Unwrap the phase along subcarriers (axis=1)
    phase_unwrapped = np.unwrap(phase_raw, axis=1)

    # 2. Vectorized linear fit subtraction across subcarriers
    x = np.arange(n_subcarriers, dtype=np.float64)
    x_mean = np.mean(x)
    x_diff = x - x_mean
    x_var = np.sum(x_diff ** 2)

    if x_var == 0:
        return phase_unwrapped

    # Mean of unwrapped phase per packet (shape: n_packets, 1)
    y_mean = np.mean(phase_unwrapped, axis=1, keepdims=True)
    y_diff = phase_unwrapped - y_mean

    # Calculate slope and intercept for each packet (vectorized)
    slope = np.sum(y_diff * x_diff, axis=1, keepdims=True) / x_var
    intercept = y_mean - slope * x_mean

    # Compute calibrated phase: theta_cal = theta_unwrap - (slope * x + intercept)
    calibrated_phase = phase_unwrapped - (slope * x + intercept)

    return calibrated_phase
