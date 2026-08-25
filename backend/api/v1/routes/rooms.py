from __future__ import annotations

import os
import random
import shutil
import tempfile
import json
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from database.db import get_session
from database.models import Room
from fingerprint_database.fingerprint_manager import FingerprintManager

router = APIRouter(tags=["rooms"])


class RoomCreate(BaseModel):
    name: str


@router.get("/rooms")
def list_rooms() -> List[Dict[str, Any]]:
    try:
        data = FingerprintManager.export_dataset()
        return json.loads(data)
    except Exception as e:
        return []


@router.post("/rooms")
def create_room(payload: RoomCreate) -> Dict[str, Any]:
    try:
        room = FingerprintManager.create_room(payload.name)
        return {"id": room.id, "name": room.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
def reset_all_data() -> Dict[str, Any]:
    try:
        FingerprintManager.reset_database()
        return {"status": "success", "message": "All rooms, positions, fingerprints, and CSI samples deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/rooms/{room_id}")
def delete_room(room_id: int) -> Dict[str, Any]:
    try:
        FingerprintManager.delete_room(room_id)

        bp_dir = os.path.join("assets", "blueprints", str(room_id))
        if os.path.exists(bp_dir):
            shutil.rmtree(bp_dir, ignore_errors=True)

        return {"status": "success", "message": f"Room {room_id} deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/blueprints")
async def upload_blueprint(room_id: int, file: UploadFile = File(...)) -> Dict[str, Any]:
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"temp_blueprint_{random.randint(1000, 9999)}_{file.filename}")

    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        blueprint = FingerprintManager.save_blueprint(
            room_id=room_id,
            image_path=temp_file_path,
            upload_dir="assets/blueprints"
        )
        return {
            "id": blueprint.id,
            "room_id": blueprint.room_id,
            "file_path": blueprint.file_path,
            "width_px": blueprint.width_px,
            "height_px": blueprint.height_px
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
