# API Reference

## `GET /health`

Returns service health and a UTC timestamp.

## `POST /localize`

Request:

```json
{
  "room_id": "room-04",
  "csi_window_id": "window-001"
}
```

Response includes the predicted zone, confidence, motion state, and a note that the result is an estimate from CSI fingerprints.

## `GET /motion/events`

Returns recent motion events for the dashboard.
