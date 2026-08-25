from __future__ import annotations

import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.api.v1.routes.websocket import generate_telemetry_loop
from backend.core.config import settings
from database.db import init_db

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description=settings.description,
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure assets directory exists for serving blueprints and position images
os.makedirs("assets", exist_ok=True)
os.makedirs("assets/blueprints", exist_ok=True)
os.makedirs("assets/positions", exist_ok=True)

app.mount("/assets", StaticFiles(directory="assets"), name="assets")

app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    # Initialize real database schema for SQLite storage
    init_db("sqlite:///database/wifisense.db")

    # Start UDP CSI Receiver background thread on port 5566
    config_path = os.path.join("python_receiver", "config.yaml")
    if os.path.exists(config_path):
        try:
            from python_receiver.udp_server import CSIPacketReceiver
            receiver = CSIPacketReceiver(config_path)
            receiver.start()
        except Exception as e:
            print(f"UDP Receiver startup warning: {e}")

    # Launch background telemetry generator loop
    asyncio.create_task(generate_telemetry_loop())
