"""
Frequency and time-frequency transforms for CSI.
Includes Fast Fourier Transform (FFT) and Discrete Wavelet Transform (DWT).
"""

from typing import List, Tuple
import numpy as np
import pywt


def fft(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes the Fast Fourier Transform (FFT) along the time axis (axis=0) of the CSI signal.
    
    Args:
        x: Array of shape (n_packets, n_subcarriers)
        
    Returns:
        magnitude: Absolute magnitude of FFT coefficients
        phase: Phase angle of FFT coefficients
    """
    if x.shape[0] == 0:
        return np.empty_like(x), np.empty_like(x)

    # Compute FFT along the time axis (axis=0)
    X = np.fft.fft(x, axis=0)
    
    magnitude = np.abs(X)
    phase = np.angle(X)
    
    return magnitude, phase


def dwt(x: np.ndarray, wavelet: str = "db4", level: int = 4) -> List[np.ndarray]:
    """
    Computes the Discrete Wavelet Transform (DWT) along the time axis (axis=0) of the CSI signal.
    
    Args:
        x: Array of shape (n_packets, n_subcarriers)
        wavelet: Wavelet name (e.g. 'db4')
        level: Decomposition level
        
    Returns:
        coefficients: List of decomposition coefficients [cA_n, cD_n, cD_n-1, ..., cD_1]
    """
    if x.shape[0] == 0:
        return []

    # Adjust decomposition level if the signal is too short
    max_level = pywt.dwt_max_level(data_len=x.shape[0], filter_len=pywt.Wavelet(wavelet).dec_len)
    actual_level = min(level, max_level)
    
    if actual_level <= 0:
        # If signal is too short for decomposition, return it as the single approximation coefficient
        return [x.copy()]

    # Compute multi-level 1D wavelet decomposition along axis=0
    return pywt.wavedec(x, wavelet, level=actual_level, axis=0)
