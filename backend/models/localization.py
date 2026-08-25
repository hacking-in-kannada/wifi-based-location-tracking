from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocalizationResult:
    room_id: str
    predicted_zone: str
    confidence: float
    motion_state: str
    note: str
