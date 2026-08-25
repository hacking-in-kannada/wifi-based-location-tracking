# Architecture Overview

## System summary

WiFiSense is designed around a CSI pipeline that collects Wi-Fi channel measurements from an ESP32-CAM receiver with the camera disabled, processes those readings in Python, and uses fingerprinting models to estimate the closest trained room position.

## Core flow

1. ESP32-CAM captures CSI and metadata.
2. Python receiver ingests and buffers packets.
3. Signal-processing cleans and normalizes the stream.
4. Feature extraction builds fixed-length vectors.
5. Fingerprint storage persists labeled samples.
6. ML models predict the nearest trained zone.
7. FastAPI exposes data to the dashboard.
8. The web UI renders position, confidence, and motion state.

## Accuracy guidance

The system is intentionally framed as zone classification and fingerprint matching. It should not claim precise real-time coordinates unless a future sensing stack supports that level of accuracy.

## Proposed module layout

- `firmware/` for ESP-IDF CSI receiver code
- `python_receiver/` for UDP ingestion and persistence
- `signal_processing/` for filtering and calibration
- `feature_extraction/` for statistical and temporal features
- `machine_learning/` for model training and inference
- `fingerprint_database/` for room and sample records
- `backend/` for API, auth, and orchestration
- `frontend/` for dashboard UI

## Data model sketch

- Rooms
- Blueprints
- Fingerprints
- CSI packets
- Feature vectors
- Predictions
- Motion events
- Models

