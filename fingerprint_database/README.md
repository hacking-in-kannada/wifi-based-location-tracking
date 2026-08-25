# WiFiSense Fingerprint Database

This module coordinates room, blueprint, and position configuration alongside CSI fingerprint collection and persistence.

## Workflow

1. **Room Creation & Blueprint Upload**:
   - Save the room's blueprint image (PNG/JPG) under `assets/blueprints/{room_id}/`.
   - Read image dimensions to calibrate pixel coordinate offsets.
   
2. **Zone / Position Marking**:
   - Users select coordinates `(blueprint_x, blueprint_y)` on the canvas overlay.
   - A labeled zone (e.g. "Living Room Couch") is registered in the database `positions` table.
   
3. **Capture Fingerprints**:
   - Once a zone is clicked, a 10-second capture window is pulled from the receiver's memory buffer.
   - The raw data packets are converted to an amplitude matrix, denoised, and z-scored.
   - Sliding 1-second features are computed (50% overlap) generating multiple `FingerprintSample` entries.
   
4. **Materialize Averages**:
   - The system automatically re-averages the feature vectors of all samples associated with a given `position_id`, updating the `Fingerprint` record with the mean vector and new `sample_count`.

## DB Tables Managed

- `rooms`: ID and friendly name.
- `blueprints`: Image file paths and pixel resolutions.
- `positions`: Click coordinates and friendly labels.
- `fingerprints`: Averaged feature vectors and sample counts.
- `fingerprint_samples`: Individual raw capture feature sets.

## Import / Export

Datasets can be exported and imported as a single bundled JSON payload.
