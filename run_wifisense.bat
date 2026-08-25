@echo off
title WiFiSense Launcher
echo ============================================================
echo           Starting WiFiSense Indoor Motion System
echo ============================================================
echo.

:: 1. Start Backend FastAPI Server in a new window
echo [1/3] Starting FastAPI Backend Server on http://127.0.0.1:8000...
start "WiFiSense Backend (Port 8000)" cmd /k "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

:: 2. Start Frontend Dev Server in a new window
echo [2/3] Starting Vite Frontend Dev Server on http://localhost:5173...
start "WiFiSense Frontend (Port 5173)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: 3. Open Browser after short delay
echo [3/3] Launching web browser...
ping -n 4 127.0.0.1 >nul
start http://localhost:5173/

echo.
echo ============================================================
echo WiFiSense Services Launched!
echo.
echo  - Dashboard: http://localhost:5173/
echo  - API Docs:  http://127.0.0.1:8000/docs
echo ============================================================
echo.
