from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CSIFrame:
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

    @property
    def subcarrier_count(self) -> int:
        return len(self.amplitude)
