# Localization Model Performance Report

This report evaluates the accuracy, macro F1, and inference latency of the four CSI zone localization classifiers using 5-fold cross-validation on a synthetic 5-position fingerprint dataset.

## Performance Summary

| Model | Accuracy (Mean) | Macro F1 (Mean) | Inference Latency (Mean) |
|---|---|---|---|
| KNN | 100.00% | 1.0000 | 12.52 ms |
| Random Forest | 100.00% | 1.0000 | 4.65 ms |
| SVM | 100.00% | 1.0000 | 0.17 ms |
| Neural Network (MLP) | 100.00% | 1.0000 | 0.11 ms |

> [!IMPORTANT]
> WiFiSense classification estimations represent **closest matching trained zone/locations** only. The system is designed to classify rooms/zones rather than resolve exact centimeter-level spatial coordinates.

## Confusion Matrices

Values show the normalized prediction distribution (actual vs predicted) across the 5 training positions:

### KNN Confusion Matrix

```
[[1., 0., 0., 0., 0.],
 [0., 1., 0., 0., 0.],
 [0., 0., 1., 0., 0.],
 [0., 0., 0., 1., 0.],
 [0., 0., 0., 0., 1.]]
```

### Random Forest Confusion Matrix

```
[[1., 0., 0., 0., 0.],
 [0., 1., 0., 0., 0.],
 [0., 0., 1., 0., 0.],
 [0., 0., 0., 1., 0.],
 [0., 0., 0., 0., 1.]]
```

### SVM Confusion Matrix

```
[[1., 0., 0., 0., 0.],
 [0., 1., 0., 0., 0.],
 [0., 0., 1., 0., 0.],
 [0., 0., 0., 1., 0.],
 [0., 0., 0., 0., 1.]]
```

### Neural Network (MLP) Confusion Matrix

```
[[1., 0., 0., 0., 0.],
 [0., 1., 0., 0., 0.],
 [0., 0., 1., 0., 0.],
 [0., 0., 0., 1., 0.],
 [0., 0., 0., 0., 1.]]
```

