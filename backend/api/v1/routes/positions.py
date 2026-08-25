from __future__ import annotations

import os
import shutil
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from database.db import get_session
from database.models import Position
from fingerprint_database.fingerprint_manager import FingerprintManager

router = APIRouter(tags=["positions"])


class PositionCreate(BaseModel):
    room_id: int
    label: str
    x: int
    y: int


@router.post("/positions")
def create_position(payload: PositionCreate) -> Dict[str, Any]:
    try:
        pos = FingerprintManager.create_position(
            room_id=payload.room_id,
            label=payload.label,
            x=payload.x,
            y=payload.y
        )
        return {
            "id": pos.id,
            "room_id": pos.room_id,
            "label": pos.label,
            "x": pos.blueprint_x,
            "y": pos.blueprint_y,
            "image_path": pos.image_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/positions/{position_id}")
def delete_position(position_id: int) -> Dict[str, Any]:
    try:
        FingerprintManager.delete_position(position_id)
        
        # Purge assets directory for this position if it exists
        target_dir = os.path.join("assets", "positions", str(position_id))
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)

        return {"status": "success", "message": f"Position {position_id} deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions/{position_id}/image")
async def upload_position_image(position_id: int, file: UploadFile = File(...)) -> Dict[str, Any]:
    upload_dir = "assets/positions"
    target_dir = os.path.join(upload_dir, str(position_id))
    os.makedirs(target_dir, exist_ok=True)

    filename = file.filename or "image.jpg"
    safe_filename = "".join(c for c in filename if c.isalnum() or c in (".", "_", "-"))
    dest_path = f"assets/positions/{position_id}/{safe_filename}"

    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        session = get_session()
        pos = session.query(Position).filter_by(id=position_id).first()
        if not pos:
            raise HTTPException(status_code=404, detail="Position not found")

        pos.image_path = dest_path.replace("\\", "/")
        session.commit()
        session.refresh(pos)
        image_path = pos.image_path
        session.close()

        return {"status": "success", "image_path": image_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/positions/{position_id}/image")
def delete_position_image(position_id: int) -> Dict[str, Any]:
    try:
        session = get_session()
        pos = session.query(Position).filter_by(id=position_id).first()
        if not pos:
            raise HTTPException(status_code=404, detail="Position not found")

        if pos.image_path and os.path.exists(pos.image_path):
            try:
                os.remove(pos.image_path)
            except Exception:
                pass

        pos.image_path = None
        session.commit()
        session.close()

        target_dir = os.path.join("assets", "positions", str(position_id))
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir, ignore_errors=True)

        return {"status": "success", "message": f"Image removed for position {position_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
