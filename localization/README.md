# WiFiSense Localization Module

This directory contains the classifier models and smoothing pipelines for mapping real-time CSI feature vectors to trained room zones.

## Core Components

1. **`base.py`**:
   - Declares the abstract base class `LocalizationModel`. All algorithms implement this interface to allow hot-swappable model architectures.
   
2. **`knn.py`**:
   - `KNNLocalizer`: Distance-weighted K-Nearest Neighbors. Offers fast training and robust zone-boundary classification.
   
3. **`random_forest.py`**:
   - `RandomForestLocalizer`: Multi-decision-tree ensemble. Extremely robust to noise features.
   
4. **`svm.py`**:
   - `SVMLocalizer`: Support Vector Machine with probability scaling (Platt scaling) for accurate confidence metrics.
   
5. **`neural_net.py`**:
   - `NeuralNetLocalizer`: PyTorch Multi-Layer Perceptron (MLP) consisting of `InputDim -> 64 -> 32 -> OutputClasses` fully connected layers.
   
6. **`smoothing.py`**:
   - `PredictionSmoother`: A rolling deque of the last $K$ predictions (default 5). Averages the probability maps to reduce rapid state switches (flickering).

## Calibration and Framing Rules

- **Estimated Zones**: All localization outputs are framed as "closest matching trained zone/location", not centimeter-level radar coordinates.
- **Calibrated Confidence**: Outputs always associate the predicted zone with its probability/confidence score (e.g., `(Zone A, 87%)`).
