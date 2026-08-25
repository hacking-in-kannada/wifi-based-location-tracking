from datetime import datetime, timezone

from backend.models.csi import CSIFrame
from backend.services.localization import LocalizationService


def test_predict_returns_zone_and_confidence() -> None:
    service = LocalizationService()
    frame = CSIFrame(
        timestamp=datetime.now(timezone.utc),
        rssi=-44.0,
        mac_address="AA:BB:CC:DD:EE:FF",
        channel=6,
        bandwidth_mhz=20,
        amplitude=(0.2, 0.4, 0.6, 0.8),
        phase=(1.0, 1.2, 1.4, 1.6),
    )

    result = service.predict("room-04", "window-001", frame)

    assert result.room_id == "room-04"
    assert result.predicted_zone == "North Desk"
    assert 0.65 <= result.confidence <= 0.97
