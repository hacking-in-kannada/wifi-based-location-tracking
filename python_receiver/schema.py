from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class CSIPacket:
    timestamp: datetime
    rssi: float
    mac_address: str
    channel: int
    bandwidth_mhz: int
    amplitude: tuple[float, ...]
    phase: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.mac_address.strip():
            raise ValueError("mac_address must not be empty")
        if self.channel <= 0:
            raise ValueError("channel must be positive")
        if self.bandwidth_mhz <= 0:
            raise ValueError("bandwidth_mhz must be positive")
        if not self.amplitude:
            raise ValueError("amplitude must contain at least one subcarrier")
        if len(self.amplitude) != len(self.phase):
            raise ValueError("amplitude and phase must have the same length")


def parse_csi_packet(payload: bytes) -> CSIPacket:
    raw = json.loads(payload.decode("utf-8"))

    timestamp_value = raw.get("timestamp")
    timestamp = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00")) if timestamp_value else datetime.now(timezone.utc)

    return CSIPacket(
        timestamp=timestamp,
        rssi=float(raw["rssi"]),
        mac_address=str(raw["mac_address"]),
        channel=int(raw["channel"]),
        bandwidth_mhz=int(raw["bandwidth_mhz"]),
        amplitude=tuple(float(value) for value in raw["amplitude"]),
        phase=tuple(float(value) for value in raw["phase"]),
    )
