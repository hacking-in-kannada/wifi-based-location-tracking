from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health_route() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_localize_route() -> None:
    response = client.post(
        "/localize",
        json={"room_id": "room-04", "csi_window_id": "window-001"},
    )

    assert response.status_code == 200
    assert response.json()["predicted_zone"] == "North Desk"
