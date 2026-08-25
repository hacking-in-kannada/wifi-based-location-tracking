# WiFiSense Signal Processing Module

This directory contains pure signal processing functions operating on NumPy arrays of shape `(n_packets, n_subcarriers)`.

## Module Components

1. **`denoise.py`**:
   - `moving_average(x, window)`: Sliding window filter to remove high-frequency noise.
   - `butterworth_lowpass(x, cutoff_hz, sample_rate_hz, order)`: Zero-phase lowpass Butterworth filter to smooth the CSI amplitude.
   - `median_filter(x, kernel_size)`: Running median filter to eliminate impulse spike anomalies.
   
2. **`calibration.py`**:
   - `phase_unwrap_and_calibrate(phase_raw)`: Unwraps raw phase angles along the subcarrier axis (using `np.unwrap`), and fits a linear regression across the subcarrier indices to subtract timing/sampling frequency offsets (SFO/CFO).
   
3. **`normalization.py`**:
   - `amplitude_normalize(amp, method)`: Standardizes CSI amplitudes per-packet using either z-score or min-max normalization.
   
4. **`outliers.py`**:
   - `remove_outliers(x, method, threshold)`: Identifies outliers along the packet time series (using z-score or IQR thresholds) and replaces them with subcarrier median values.
   
5. **`transforms.py`**:
   - `fft(x)`: Fast Fourier Transform mapping signal components to the frequency domain (magnitude & phase).
   - `dwt(x, wavelet, level)`: Multiresolution Discrete Wavelet Transform using PyWavelets.
   
6. **`visualization.py`**:
   - `plot_amplitude_heatmap(amp, save_path)`: Draws 2D heatmaps of CSI amplitude.
   - `plot_phase_over_time(phase, save_path)`: Draws line plots of CSI phase over time.

## Mathematical Formulation: Phase Calibration

To cancel SFO/CFO phase distortion on subcarrier index $k$, the raw phase $\theta_k$ is unwrapped to $\theta'_k$. Then we perform linear regression:
$$\theta'_k = a \cdot k + b$$
The calibrated phase $\hat{\theta}_k$ is obtained by removing this trend:
$$\hat{\theta}_k = \theta'_k - a \cdot k - b$$
This calculation is fully vectorized across all packets for high performance.
