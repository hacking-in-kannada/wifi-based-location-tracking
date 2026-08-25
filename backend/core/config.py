from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project_name: str = "WiFiSense API"
    version: str = "0.1.0"
    description: str = "CSI fingerprinting and motion localization backend"


settings = Settings()
