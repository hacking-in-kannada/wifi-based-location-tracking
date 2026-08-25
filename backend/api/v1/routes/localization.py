from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services.localization import LocalizationService

router = APIRouter(tags=["localization"])
service = LocalizationService()


class LocalizeRequest(BaseModel):
    room_id: str = Field(min_length=1)
    csi_window_id: str = Field(min_length=1)


class LocalizeResponse(BaseModel):
    room_id: str
    predicted_zone: str
    confidence: float
    motion_state: str
    note: str


@router.post("/localize", response_model=LocalizeResponse)
def localize(payload: LocalizeRequest) -> LocalizeResponse:
    result = service.predict(
        room_id=payload.room_id,
        csi_window_id=payload.csi_window_id,
    )
    return LocalizeResponse(**vars(result))
