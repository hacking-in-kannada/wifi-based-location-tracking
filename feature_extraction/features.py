"""
CSI Feature Extraction module.
Extracts statistical, frequency-domain, temporal, and aggregate features 
from sliding windows of processed CSI amplitude.
"""

from dataclasses import dataclass, asdict
import json
from typing import Dict, Any, List
import numpy as np
import scipy.stats
from scipy.signal import find_peaks


@dataclass
class FeatureVector:
    """
    Structured dataclass representing the flat feature vector for a CSI window.
    """
    timestamp_start: float
    timestamp_end: float
    features_dict: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the feature vector into a flat dictionary suitable for DB / CSV rows.
        """
        result = {
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
        }
        result.update(self.features_dict)
        return result


def extract_window_features(
    csi_window: np.ndarray,
    timestamp_start: float,
    timestamp_end: float,
    sample_rate_hz: float = 50.0
) -> FeatureVector:
    """
    Extracts features from a (n_packets, n_subcarriers) CSI amplitude window.
    
    Args:
        csi_window: Array of shape (n_packets, n_subcarriers) containing CSI amplitudes.
        timestamp_start: Start timestamp of the window (seconds).
        timestamp_end: End timestamp of the window (seconds).
        sample_rate_hz: Ingestion rate of CSI packets.
        
    Returns:
        feature_vector: FeatureVector object.
    """
    n_packets, n_subcarriers = csi_window.shape
    features_dict = {}

    if n_packets <= 1:
        # Return empty or default features if window is too small
        return FeatureVector(timestamp_start, timestamp_end, {})

    # 1. Statistical Features
    mean = np.mean(csi_window, axis=0)
    variance = np.var(csi_window, axis=0)
    std = np.std(csi_window, axis=0)
    
    # Skewness and Kurtosis with nan protection
    skew = scipy.stats.skew(csi_window, axis=0, bias=False)
    skew = np.nan_to_num(skew, nan=0.0)
    
    kurt = scipy.stats.kurtosis(csi_window, axis=0, bias=False)
    kurt = np.nan_to_num(kurt, nan=0.0)

    energy = np.sum(csi_window ** 2, axis=0)

    # Shannon Entropy of amplitude histograms
    entropy = []
    for col in range(n_subcarriers):
        col_data = csi_window[:, col]
        min_val, max_val = col_data.min(), col_data.max()
        if max_val - min_val < 1e-6:
            ent = 0.0
        else:
            hist, _ = np.histogram(col_data, bins=10, range=(min_val, max_val))
            p = hist / (hist.sum() + 1e-8)
            ent = -np.sum(p * np.log2(p + 1e-8))
        entropy.append(ent)
    entropy = np.array(entropy)

    # Peak Counts
    peak_counts = []
    for col in range(n_subcarriers):
        peaks, _ = find_peaks(csi_window[:, col])
        peak_counts.append(float(len(peaks)))
    peak_counts = np.array(peak_counts)

    # 2. Frequency-domain Features (via FFT)
    mag = np.abs(np.fft.fft(csi_window, axis=0))
    half_len = n_packets // 2
    mag_half = mag[:half_len, :]
    freqs = np.fft.fftfreq(n_packets, d=1.0/sample_rate_hz)[:half_len]

    # Dominant Frequency (excluding DC component)
    dominant_freqs = []
    for col in range(n_subcarriers):
        col_mag = mag_half[1:, col] if half_len > 1 else np.array([])
        if len(col_mag) > 0 and np.sum(col_mag) > 0:
            dom_idx = np.argmax(col_mag) + 1
            dom_freq = freqs[dom_idx]
        else:
            dom_freq = 0.0
        dominant_freqs.append(dom_freq)
    dominant_freqs = np.array(dominant_freqs)

    # Spectral Centroid
    centroid = np.sum(freqs[:, np.newaxis] * mag_half, axis=0) / (np.sum(mag_half, axis=0) + 1e-8)

    # Band Energy Ratios (excluding DC index 0)
    low_mask = (freqs > 0) & (freqs <= 2.5)
    med_mask = (freqs > 2.5) & (freqs <= 10.0)
    high_mask = (freqs > 10.0)

    total_energy_fft = np.sum(mag_half[1:, :] ** 2, axis=0) + 1e-8
    low_energy_ratio = np.sum(mag_half[low_mask, :] ** 2, axis=0) / total_energy_fft
    med_energy_ratio = np.sum(mag_half[med_mask, :] ** 2, axis=0) / total_energy_fft
    high_energy_ratio = np.sum(mag_half[high_mask, :] ** 2, axis=0) / total_energy_fft

    # 3. Temporal Features
    diffs = np.diff(csi_window, axis=0)
    diff_mean = np.mean(np.abs(diffs), axis=0)
    diff_std = np.std(diffs, axis=0)

    # Autocorrelation Lag-1
    autocorr = []
    for col in range(n_subcarriers):
        col_data = csi_window[:, col]
        col_std = np.std(col_data)
        if col_std < 1e-8:
            r = 0.0
        else:
            r = np.corrcoef(col_data[:-1], col_data[1:])[0, 1]
            if np.isnan(r):
                r = 0.0
        autocorr.append(r)
    autocorr = np.array(autocorr)

    # 4. Populate flat dictionary for per-subcarrier features
    for j in range(n_subcarriers):
        features_dict[f"mean_sc_{j}"] = float(mean[j])
        features_dict[f"var_sc_{j}"] = float(variance[j])
        features_dict[f"std_sc_{j}"] = float(std[j])
        features_dict[f"skew_sc_{j}"] = float(skew[j])
        features_dict[f"kurt_sc_{j}"] = float(kurt[j])
        features_dict[f"energy_sc_{j}"] = float(energy[j])
        features_dict[f"entropy_sc_{j}"] = float(entropy[j])
        features_dict[f"peaks_sc_{j}"] = float(peak_counts[j])
        features_dict[f"dom_freq_sc_{j}"] = float(dominant_freqs[j])
        features_dict[f"centroid_sc_{j}"] = float(centroid[j])
        features_dict[f"low_ratio_sc_{j}"] = float(low_energy_ratio[j])
        features_dict[f"med_ratio_sc_{j}"] = float(med_energy_ratio[j])
        features_dict[f"high_ratio_sc_{j}"] = float(high_energy_ratio[j])
        features_dict[f"diff_mean_sc_{j}"] = float(diff_mean[j])
        features_dict[f"diff_std_sc_{j}"] = float(diff_std[j])
        features_dict[f"autocorr_sc_{j}"] = float(autocorr[j])

    # 5. Populate aggregate features (mean of each feature type across all subcarriers)
    features_dict["agg_mean"] = float(np.mean(mean))
    features_dict["agg_variance"] = float(np.mean(variance))
    features_dict["agg_std"] = float(np.mean(std))
    features_dict["agg_skewness"] = float(np.mean(skew))
    features_dict["agg_kurtosis"] = float(np.mean(kurt))
    features_dict["agg_energy"] = float(np.mean(energy))
    features_dict["agg_entropy"] = float(np.mean(entropy))
    features_dict["agg_peaks"] = float(np.mean(peak_counts))
    features_dict["agg_dom_freq"] = float(np.mean(dominant_freqs))
    features_dict["agg_centroid"] = float(np.mean(centroid))
    features_dict["agg_low_ratio"] = float(np.mean(low_energy_ratio))
    features_dict["agg_med_ratio"] = float(np.mean(med_energy_ratio))
    features_dict["agg_high_ratio"] = float(np.mean(high_energy_ratio))
    features_dict["agg_diff_mean"] = float(np.mean(diff_mean))
    features_dict["agg_diff_std"] = float(np.mean(diff_std))
    features_dict["agg_autocorr"] = float(np.mean(autocorr))

    return FeatureVector(timestamp_start, timestamp_end, features_dict)
