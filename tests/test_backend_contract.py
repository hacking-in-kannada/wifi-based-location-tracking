from backend.main import app


def test_routes_exist() -> None:
    route_paths = {route.path for route in app.routes}

    assert "/health" in route_paths
    assert "/localize" in route_paths
    assert "/motion/events" in route_paths
