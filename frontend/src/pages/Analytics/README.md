# Phase 10: Analytics Dashboard

Adds a real-time analytics view to the WiFiSense frontend, summarizing the health
of the training dataset, model benchmark results, and hardware signal quality.

## Features

### KPI Cards
| Card | Metric |
|---|---|
| Total Samples | Aggregate samples across all trained positions |
| Dataset Complete | % of positions with materialized fingerprints |
| Best Accuracy | Highest cross-validated accuracy across 4 models |
| Fastest Inference | Minimum latency model (SVM/KNN sub-ms) |

### Charts (pure SVG — no external library)
| Chart | Description |
|---|---|
| 30-Day Accuracy Trend | Polyline chart with gradient fill showing rolling accuracy history |
| Model Benchmark | Horizontal bars comparing KNN / SVM / RF / Neural Net |
| Inference Latency | Sorted latency bars showing ms-per-prediction |
| Zone Coverage | Per-position sample counts vs 150-sample target |
| RSSI Distribution | Histogram of received signal strength buckets |

## API Endpoint

```
GET /api/v1/analytics
```

Returns:
```json
{
  "summary": { "total_rooms": 1, "total_positions": 5, "total_samples": 674, "trained_positions": 4, "dataset_completeness_pct": 80.0 },
  "model_benchmarks": [{"name": "SVM (RBF)", "accuracy": 97.2, "f1": 0.972, "latency_ms": 0.18, "color": "#34d399"}, ...],
  "zone_coverage": [{"room": "...", "label": "...", "sample_count": 150, "has_fingerprint": true}, ...],
  "accuracy_history": [{"day": 1, "accuracy": 88.5}, ...],
  "rssi_distribution": [{"range": "-65 to -60 dBm", "count": 62}, ...]
}
```

## Accuracy Disclaimer

> Zone predictions represent **closest matching trained location** — not centimeter GPS coordinates.
> Confidence scores accompany every prediction.
> Minimum: 100 samples/zone, 3+ zones, 64 subcarriers (HT20 / 2.4 GHz).

## File Locations

- Frontend: `frontend/src/pages/Analytics/Analytics.tsx`
- Backend endpoint: `scripts/mock_stream.py` → `GET /api/v1/analytics`
