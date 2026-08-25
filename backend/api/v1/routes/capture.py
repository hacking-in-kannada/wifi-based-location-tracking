from __future__ import annotations

import asyncio
import datetime
import struct
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from database.db import get_session
from database.models import CSIPacket
from fingerprint_database.fingerprint_manager import FingerprintManager
from python_receiver.packet_parser import PacketParser
from tests.synthetic_udp_sender import generate_mock_packet

router = APIRouter(tags=["capture"])


class CaptureRequest(BaseModel):
    room_id: int
    position_id: int
    duration_sec: int = 10  # How many seconds to capture ambient CSI at this device location

    @field_validator("room_id", "position_id", mode="before")
    @classmethod
    def coerce_int(cls, v):
        if v is None or v == "":
            raise ValueError("ID cannot be empty")
        return int(v)


@router.post("/capture")
async def trigger_capture(payload: CaptureRequest) -> Dict[str, Any]:
    """
    Capture ambient CSI fingerprint at the device's current resting location.
    
    DEVICE LOCALIZATION MODE:
    - Place the ESP32-CAM device at the target location and keep it STILL.
    - Start this capture — it records the ambient Wi-Fi CSI signature for that spot.
    - When the device is later moved, the system compares live CSI to stored
      fingerprints and predicts which location the device is now at.
    """
    start_time = datetime.datetime.utcnow()
    duration_sec = max(5, min(30, payload.duration_sec))  # Clamp between 5-30s

    # Wait for the device to settle and collect ambient CSI at its location
    await asyncio.sleep(duration_sec)

    session = get_session()
    message_type = "REAL"
    packets = []
    try:
        db_packets = (
            session.query(CSIPacket)
            .filter(CSIPacket.created_at >= start_time)
            .order_by(CSIPacket.id.asc())
            .all()
        )

        if len(db_packets) >= 50:
            for p in db_packets:
                csi_data = list(struct.unpack(f"{len(p.raw_blob)}b", p.raw_blob))
                packets.append({
                    "seq_no": p.seq_no,
                    "mac": p.mac,
                    "rssi": p.rssi,
                    "channel": p.channel,
                    "bandwidth": p.bandwidth,
                    "timestamp_us": p.timestamp_us,
                    "csi_len": len(csi_data),
                    "csi_data": csi_data,
                })
        else:
            # Fallback to mock data if no real packets were received
            parser = PacketParser()
            for step in range(1, duration_sec + 1):
                for i in range(50):
                    raw = generate_mock_packet(step * 50 + i)
                    parsed = parser.parse(raw)
                    if parsed is not None:
                        packets.append(parsed)
            message_type = "MOCK (No real packets — check ESP32 is on and connected)"
    except Exception as e:
        parser = PacketParser()
        for step in range(1, 11):
            for i in range(50):
                raw = generate_mock_packet(step * 50 + i)
                parsed = parser.parse(raw)
                if parsed is not None:
                    packets.append(parsed)
        message_type = f"MOCK (Fallback due to error: {e})"
    finally:
        session.close()

    try:
        sample_ids = FingerprintManager.capture_fingerprint(
            room_id=payload.room_id,
            position_id=payload.position_id,
            packets=packets,
            sample_rate_hz=50.0
        )

        real_count = len([p for p in packets if isinstance(p, dict) and "rssi" in p])
        return {
            "status": "success",
            "sample_count": len(sample_ids),
            "packet_count": len(packets),
            "source": message_type,
            "message": (
                f"Device location fingerprint captured from {len(packets)} CSI frames "
                f"over {duration_sec}s using {message_type} data. "
                f"{len(sample_ids)} feature windows stored."
            )
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
