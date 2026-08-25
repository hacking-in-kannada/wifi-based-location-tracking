"""
Unit tests for the CSI signal processing pipeline.
Verifies noise reduction, phase unwrapping and calibration, normalization,
and outlier removal functions.
"""

import unittest
import numpy as np

from signal_processing.denoise import moving_average, butterworth_lowpass, median_filter
from signal_processing.calibration import phase_unwrap_and_calibrate
from signal_processing.normalization import amplitude_normalize
from signal_processing.outliers import remove_outliers
from signal_processing.transforms import fft, dwt


class TestSignalProcessing(unittest.TestCase):
    def test_noise_reduction_filters(self):
        """
        Verifies that moving average, Butterworth, and median filters
        reduce injected Gaussian noise variance by a measurable margin.
        """
        np.random.seed(42)
        n_packets = 200
        n_subcarriers = 30
        
        # 1. Generate clean synthetic CSI amplitude (constant base + slow wave)
        t = np.linspace(0, 10, n_packets)[:, np.newaxis]
        clean_csi = 5.0 + 2.0 * np.sin(t) * np.ones((1, n_subcarriers))

        # 2. Inject high-frequency Gaussian noise
        noise = np.random.normal(0, 0.8, size=clean_csi.shape)
        noisy_csi = clean_csi + noise
        
        var_before = np.var(noisy_csi - clean_csi)

        # 3. Apply Moving Average Filter
        ma_filtered = moving_average(noisy_csi, window=9)
        var_after_ma = np.var(ma_filtered - clean_csi)
        
        # 4. Apply Butterworth Filter
        bw_filtered = butterworth_lowpass(noisy_csi, cutoff_hz=2.0, sample_rate_hz=50.0)
        var_after_bw = np.var(bw_filtered - clean_csi)

        # 5. Apply Median Filter
        med_filtered = median_filter(noisy_csi, kernel_size=9)
        var_after_med = np.var(med_filtered - clean_csi)

        print(f"\n--- Noise Reduction Test (Gaussian Noise Var = {var_before:.4f}) ---")
        print(f"MA Filter Residual Var:    {var_after_ma:.4f} ({(1 - var_after_ma/var_before)*100:.1f}% reduction)")
        print(f"Butter Filter Residual Var: {var_after_bw:.4f} ({(1 - var_after_bw/var_before)*100:.1f}% reduction)")
        print(f"Median Filter Residual Var:{var_after_med:.4f} ({(1 - var_after_med/var_before)*100:.1f}% reduction)")

        # Verify variance is reduced by at least 40%
        self.assertLess(var_after_ma, var_before * 0.6)
        self.assertLess(var_after_bw, var_before * 0.6)
        self.assertLess(var_after_med, var_before * 0.6)

    def test_phase_calibration(self):
        """
        Verifies that phase calibration removes an injected linear phase ramp
        (due to SFO/CFO) across subcarriers back to a near-zero flat phase.
        """
        n_packets = 50
        n_subcarriers = 64
        
        # 1. Start with flat clean phase (all zeros)
        clean_phase = np.zeros((n_packets, n_subcarriers))
        
        # 2. Inject linear phase ramps (slope and intercept differ per packet)
        injected_phase = np.zeros_like(clean_phase)
        subcarrier_indices = np.arange(n_subcarriers)
        
        for i in range(n_packets):
            slope = 0.15 + 0.05 * np.sin(i)
            intercept = -1.2 + 0.3 * np.cos(i)
            injected_phase[i] = slope * subcarrier_indices + intercept

        # 3. Calibrate
        calibrated_phase = phase_unwrap_and_calibrate(injected_phase)
        
        # Measure maximum absolute error and residual variance
        max_error = np.max(np.abs(calibrated_phase - clean_phase))
        var_calibrated = np.var(calibrated_phase)

        print(f"\n--- Phase Calibration Test ---")
        print(f"Max Absolute Error:  {max_error:.4e}")
        print(f"Calibrated Phase Var: {var_calibrated:.4e}")

        # Calibration should restore it to almost exactly 0
        self.assertLess(max_error, 1e-10)
        self.assertLess(var_calibrated, 1e-12)

    def test_amplitude_normalization(self):
        """
        Verifies z-score and min-max normalization.
        """
        np.random.seed(42)
        amp = np.random.uniform(10, 50, size=(10, 30))
        
        # Z-score: mean = 0, std = 1 per packet (along axis=1)
        z_norm = amplitude_normalize(amp, "zscore")
        np.testing.assert_array_almost_equal(z_norm.mean(axis=1), np.zeros(10), decimal=5)
        np.testing.assert_array_almost_equal(z_norm.std(axis=1), np.ones(10), decimal=5)

        # Min-max: min = 0, max = 1 per packet
        mm_norm = amplitude_normalize(amp, "minmax")
        np.testing.assert_array_almost_equal(mm_norm.min(axis=1), np.zeros(10), decimal=5)
        np.testing.assert_array_almost_equal(mm_norm.max(axis=1), np.ones(10), decimal=5)

    def test_outlier_removal(self):
        """
        Verifies outlier replacement with subcarrier medians.
        """
        np.random.seed(42)
        n_packets = 100
        n_subcarriers = 10
        
        # Base signal is constant 5.0 with low noise
        x = np.random.normal(5.0, 0.1, size=(n_packets, n_subcarriers))
        
        # Inject large spikes (outliers) in a few positions
        x[10, 2] = 50.0  # Positive spike
        x[45, 5] = -25.0  # Negative spike
        
        # Verify spikes are present
        self.assertGreater(np.max(x), 40.0)
        self.assertLess(np.min(x), -20.0)
        
        # Clean with z-score method
        cleaned_z = remove_outliers(x, method="zscore", threshold=3.0)
        self.assertLess(np.max(cleaned_z), 6.0)
        self.assertGreater(np.min(cleaned_z), 4.0)

        # Clean with iqr method
        cleaned_iqr = remove_outliers(x, method="iqr", threshold=1.5)
        self.assertLess(np.max(cleaned_iqr), 6.0)
        self.assertGreater(np.min(cleaned_iqr), 4.0)

    def test_transforms(self):
        """
        Verifies FFT and DWT execute and return expected shapes and coefficients.
        """
        x = np.random.normal(0, 1, size=(64, 30))
        
        # FFT
        mag, phase = fft(x)
        self.assertEqual(mag.shape, x.shape)
        self.assertEqual(phase.shape, x.shape)
        
        # DWT
        coeffs = dwt(x, wavelet="db4", level=3)
        self.assertEqual(len(coeffs), 4)  # cA3, cD3, cD2, cD1
        # Approximation coeff shape: (len_after_dec, n_subcarriers)
        self.assertEqual(coeffs[0].shape[1], 30)


if __name__ == "__main__":
    unittest.main()
