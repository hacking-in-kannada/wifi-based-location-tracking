from __future__ import annotations

from fastapi import APIRouter

from backend.api.v1.routes.health import router as health_router
from backend.api.v1.routes.localization import router as localization_router
from backend.api.v1.routes.motion import router as motion_router

from backend.api.v1.routes.rooms import router as rooms_router
from backend.api.v1.routes.positions import router as positions_router
from backend.api.v1.routes.capture import router as capture_router
from backend.api.v1.routes.train import router as train_router
from backend.api.v1.routes.predict import router as predict_router
from backend.api.v1.routes.analytics import router as analytics_router
from backend.api.v1.routes.websocket import router as websocket_router

api_router = APIRouter()

# Root level endpoints for backwards compatibility and tests
api_router.include_router(health_router)
api_router.include_router(localization_router)
api_router.include_router(motion_router)
api_router.include_router(websocket_router)

# Versioned API routes under /api/v1
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(rooms_router)
v1_router.include_router(positions_router)
v1_router.include_router(capture_router)
v1_router.include_router(train_router)
v1_router.include_router(predict_router)
v1_router.include_router(analytics_router)

api_router.include_router(v1_router)
