from __future__ import annotations

import asyncio
import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from machine_learning import training_pipeline
from machine_learning.inference_engine import get_engine

router = APIRouter(tags=["train"])


class TrainRequest(BaseModel):
    model: str = "auto"  # "auto" | "knn" | "svm" | "random_forest" | "neural_net"


_train_state: Dict[str, Any] = {
    "status": "idle",
    "result": None,
    "started_at": None,
}


@router.post("/train")
async def trigger_training(payload: TrainRequest) -> Dict[str, Any]:
    global _train_state
    if _train_state["status"] == "training":
        raise HTTPException(status_code=409, detail="Training already in progress.")

    _train_state = {
        "status": "training",
        "result": None,
        "started_at": datetime.datetime.now().isoformat()
    }

    async def _run():
        global _train_state
        loop = asyncio.get_event_loop()

        def _blocking_train():
            if payload.model == "auto":
                return training_pipeline.select_best_model()
            else:
                return training_pipeline.run_training(payload.model, n_cv_folds=5, save=True)

        try:
            result = await loop.run_in_executor(None, _blocking_train)
            _train_state["status"] = "done" if result.error is None else "error"
            _train_state["result"] = result.to_dict()

            if result.error is None:
                try:
                    engine = get_engine()
                    engine.load_model(result.model_name)
                except Exception:
                    pass
        except Exception as e:
            _train_state["status"] = "error"
            _train_state["result"] = {"error": str(e)}

    asyncio.create_task(_run())
    return {"status": "started", "model": payload.model}


@router.get("/train/status")
def get_training_status() -> Dict[str, Any]:
    return _train_state
