# WiFiSense Feature Extraction

This module converts windowed segments of processed CSI amplitudes into flat feature vectors.

## Feature Categories

Each window of CSI amplitudes (shape `(n_packets, n_subcarriers)`) is processed to extract:

1. **Statistical Features** (per subcarrier & aggregate):
   - **Mean**: Average signal level.
   - **Variance / Std**: Amplitude deviation (related to motion levels).
   - **Skewness**: Measure of asymmetry in distribution.
   - **Kurtosis**: Measure of peakedness in distribution.
   - **Energy**: Sum of squares representing raw signal power.
   - **Shannon Entropy**: Measures complexity of the amplitude histogram distribution.
   - **Peak Count**: Finds local maxima count using `scipy.signal.find_peaks`.

2. **Frequency-domain Features** (per subcarrier & aggregate):
   - **Dominant Frequency**: The frequency showing peak magnitude (ignoring DC bias).
   - **Spectral Centroid**: The "center of mass" of the FFT spectrum.
   - **Band Energy Ratios**: Split spectrum into Low (0-2.5 Hz), Medium (2.5-10 Hz), and High (10-25 Hz) bands to evaluate movement rates.

3. **Temporal Features** (per subcarrier & aggregate):
   - **Rate of Change (Mean/Std)**: Statistical indicators of first-order signal derivative.
   - **Lag-1 Autocorrelation**: Degree of self-similarity over successive packets.

## Schema Versioning

All outputs adhere strictly to the JSON Schema documented in [feature_schema_v1.json](feature_schema_v1.json).

## Export Formats

Features are converted into pandas DataFrames and can be serialized to:
- **CSV**: Standard comma-separated layout.
- **Apache Parquet**: Highly optimized binary format utilizing PyArrow for offline machine learning operations.
