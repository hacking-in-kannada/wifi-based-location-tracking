# WiFiSense Indoor Motion & CSI Fingerprinting

WiFiSense is a production-oriented starter for a room-scale Wi-Fi CSI fingerprinting system. The goal is to estimate the closest trained zone from CSI data and surface confidence, motion state, and signal health in a modern dashboard.

## What this repo contains

- `index.html` - a polished standalone dashboard prototype
- `styles.css` - the visual system for the interface
- `app.js` - live simulated state, charts, and blueprint rendering
- `backend/` - a FastAPI skeleton for CSI ingestion and localization
- `docs/` - architecture notes and implementation guidance

## Design goals

- Use Wi-Fi CSI only for localization
- Report estimated zones with confidence instead of exact coordinates
- Keep the architecture modular and production-friendly
- Leave room for firmware, ingestion, ML, API, and dashboard expansion

## Opening the dashboard

Open `index.html` directly in a browser. No build step is required for the current prototype.

## Backend scaffold

The backend folder provides a clean FastAPI entry point that can be extended into the full service surface described in the project brief. It now includes modular routes, a localization service, Docker support, and CI scaffolding.

## Suggested next steps

1. Connect the dashboard to real backend events over WebSocket.
2. Add firmware, receiver, and signal-processing modules.
3. Replace simulated state with persisted fingerprint and prediction data.
4. Add Docker, CI, and test coverage for the backend and frontend.

## Development stages

See [docs/stages.md](docs/stages.md) for the step-by-step project roadmap.
