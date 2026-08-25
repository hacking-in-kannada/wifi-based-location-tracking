from __future__ import annotations

from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from machine_learning.inference_engine import get_engine

router = APIRouter(tags=["predict"])


class PredictRequest(BaseModel):
    feature_vector: Dict[str, float]


@router.post("/predict")
def predict_zone(payload: PredictRequest) -> Dict[str, Any]:
    engine = get_engine()
    if not engine.is_loaded:
        try:
            engine.load_model("auto")
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail="No trained model available. POST /api/v1/train first."
            )
    try:
        result = engine.predict(payload.feature_vector)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
