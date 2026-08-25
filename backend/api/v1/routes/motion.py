from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["motion"])


class MotionEvent(BaseModel):
    event_type: str
    timestamp: datetime
    detail: str


@router.get("/motion/events", response_model=list[MotionEvent])
def motion_events() -> list[MotionEvent]:
    return [
        MotionEvent(
            event_type="motion_started",
            timestamp=datetime.now(timezone.utc),
            detail="Window variance exceeded the motion threshold.",
        )
    ]
