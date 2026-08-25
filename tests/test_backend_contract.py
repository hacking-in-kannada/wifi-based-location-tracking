from backend.main import app


def test_routes_exist() -> None:
    route_paths = {getattr(route, "path") for route in app.routes if hasattr(route, "path")}

    assert "/health" in route_paths
    assert "/localize" in route_paths
    assert "/motion/events" in route_paths
