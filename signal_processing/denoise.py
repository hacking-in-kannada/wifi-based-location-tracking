"""
Denoising filters for Channel State Information (CSI).
Includes moving average, Butterworth low-pass, and median filters.
All filters operate along the time axis (axis=0) of the input array.
"""

import numpy as np
from scipy.signal import butter, filtfilt
import scipy.ndimage


def moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """
    Applies a moving average filter along the time axis (axis=0) of x.
    Uses 'nearest' edge padding to prevent edge artifacts.
    
    Args:
        x: Array of shape (n_packets, n_subcarriers)
        window: Sliding window size
    """
    if window <= 1 or x.shape[0] <= 1:
        return x.copy()
    
    # Check if complex or real
    is_complex = np.iscomplexobj(x)
    if is_complex:
        real_part = scipy.ndimage.uniform_filter1d(x.real, size=window, axis=0, mode='nearest')
        imag_part = scipy.ndimage.uniform_filter1d(x.imag, size=window, axis=0, mode='nearest')
        return real_part + 1j * imag_part
    else:
        return scipy.ndimage.uniform_filter1d(x, size=window, axis=0, mode='nearest')


def butterworth_lowpass(x: np.ndarray, cutoff_hz: float, sample_rate_hz: float, order: int = 4) -> np.ndarray:
    """
    Applies a zero-phase Butterworth low-pass filter along the time axis (axis=0).
    
    Args:
        x: Array of shape (n_packets, n_subcarriers)
        cutoff_hz: Cutoff frequency in Hz
        sample_rate_hz: Sampling frequency in Hz
        order: Filter order
    """
    if x.shape[0] <= 1:
        return x.copy()

    # Calculate Nyquist frequency
    nyq = 0.5 * sample_rate_hz
    # Clamp cutoff to slightly below Nyquist to prevent instability
    cutoff = min(cutoff_hz, nyq * 0.99)
    normal_cutoff = cutoff / nyq

    b, a = butter(order, normal_cutoff, btype='low', analog=False)

    # filtfilt requires a minimum length of data to apply padding (typically 3 * max(len(a), len(b)))
    min_len = 3 * max(len(a), len(b))
    if x.shape[0] <= min_len:
        # Fallback to moving average if data is too short
        return moving_average(x, window=min(3, x.shape[0]))

    # Apply filter (handles complex arrays by filtering real and imaginary parts independently)
    if np.iscomplexobj(x):
        real_part = filtfilt(b, a, x.real, axis=0)
        imag_part = filtfilt(b, a, x.imag, axis=0)
        return real_part + 1j * imag_part
    else:
        return filtfilt(b, a, x, axis=0)


def median_filter(x: np.ndarray, kernel_size: int) -> np.ndarray:
    """
    Applies a 1D median filter along the time axis (axis=0) of x.
    
    Args:
        x: Array of shape (n_packets, n_subcarriers)
        kernel_size: Odd integer size of the median filter window
    """
    if kernel_size <= 1 or x.shape[0] <= 1:
        return x.copy()

    # Ensure kernel size is odd
    if kernel_size % 2 == 0:
        kernel_size += 1

    if np.iscomplexobj(x):
        real_part = scipy.ndimage.median_filter(x.real, size=(kernel_size, 1))
        imag_part = scipy.ndimage.median_filter(x.imag, size=(kernel_size, 1))
        return real_part + 1j * imag_part
    else:
        return scipy.ndimage.median_filter(x, size=(kernel_size, 1))
