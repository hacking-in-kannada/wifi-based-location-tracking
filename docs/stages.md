# Development Stages

This repository is being built in stages so each layer can be verified before the next one starts.

## Stage 1 - CSI Acquisition Backbone

Goal: define the packet format, parse CSI records, and prepare a UDP receiver path.

Deliverables:

- CSI frame model
- Packet parser and validation
- UDP receiver skeleton
- Raw frame buffering
- Stage 1 tests

## Stage 2 - Signal Processing

Goal: clean and normalize CSI streams for stable downstream features.

Deliverables:

- Moving average
- Median filter
- Phase calibration
- Amplitude normalization
- Outlier removal

## Stage 3 - Feature Extraction

Goal: convert processed CSI into model-ready feature vectors.

Deliverables:

- Statistical features
- Temporal features
- Windowed aggregation
- Feature export

## Stage 4 - Fingerprint Collection

Goal: store room blueprints, labeled locations, and CSI fingerprints.

Deliverables:

- Room records
- Blueprint uploads
- Sample collection flow
- Fingerprint persistence

## Stage 5 - Localization Engine

Goal: compare live CSI against fingerprints and estimate the closest trained zone.

Deliverables:

- KNN baseline
- Random forest baseline
- SVM baseline
- Confidence scoring
- Prediction smoothing

## Stage 6 - Motion Detection

Goal: infer movement state from CSI dynamics.

Deliverables:

- Motion start and stop detection
- Continuous motion state
- Relative direction heuristics
- Event generation

## Stage 7 - Dashboard and API Expansion

Goal: connect the UI to live backend data.

Deliverables:

- WebSocket updates
- Training dashboard actions
- Blueprint visualization
- History and model views

## Stage 8 - Packaging and Deployment

Goal: make the project reproducible and release-ready.

Deliverables:

- Docker Compose
- CI workflow
- Release notes
- Deployment guide

