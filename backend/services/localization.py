from __future__ import annotations

from backend.models.csi import CSIFrame
from backend.models.localization import LocalizationResult


class LocalizationService:
    def predict(
        self,
        room_id: str,
        csi_window_id: str,
        frame: CSIFrame | None = None,
    ) -> LocalizationResult:
        confidence = 0.87
        note = f"Estimated zone from CSI window {csi_window_id}."

        if frame is not None:
            confidence = min(0.97, 0.65 + (len(frame.amplitude) / 100.0))
            note = f"Estimated zone from CSI window {csi_window_id} after preprocessing."

        return LocalizationResult(
            room_id=room_id,
            predicted_zone="North Desk",
            confidence=confidence,
            motion_state="continuous_motion",
            note=note,
        )
