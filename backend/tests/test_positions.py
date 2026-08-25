import os
import shutil
import tempfile
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_position_crud_and_image_upload():
    # 1. Create a Room first
    room_resp = client.post("/api/v1/rooms", json={"name": "Test Room For Positions"})
    assert room_resp.status_code == 200
    room_data = room_resp.json()
    room_id = room_data["id"]

    # 2. Create a Position
    pos_resp = client.post(
        "/api/v1/positions",
        json={"room_id": room_id, "label": "Test Desk Zone", "x": 100, "y": 200},
    )
    assert pos_resp.status_code == 200
    pos_data = pos_resp.json()
    pos_id = pos_data["id"]
    assert pos_data["label"] == "Test Desk Zone"

    # 3. Upload Position Image
    # Create a dummy image file in temp
    tmp_dir = tempfile.mkdtemp()
    dummy_img_path = os.path.join(tmp_dir, "test_photo.jpg")
    with open(dummy_img_path, "wb") as f:
        f.write(b"fake image data")

    try:
        with open(dummy_img_path, "rb") as f:
            upload_resp = client.post(
                f"/api/v1/positions/{pos_id}/image",
                files={"file": ("test_photo.jpg", f, "image/jpeg")},
            )
        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        assert upload_data["status"] == "success"
        assert "assets/positions" in upload_data["image_path"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # 4. Delete the Position
    del_resp = client.delete(f"/api/v1/positions/{pos_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # 5. Delete Room
    del_room_resp = client.delete(f"/api/v1/rooms/{room_id}")
    assert del_room_resp.status_code == 200

    # 6. Database Reset Endpoint
    reset_resp = client.post("/api/v1/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "success"

