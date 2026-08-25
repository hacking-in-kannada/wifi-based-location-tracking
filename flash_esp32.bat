@echo off
title WiFiSense ESP32 Flasher
echo ============================================================
echo           Flashing WiFiSense ESP32 Firmware (COM4)
echo ============================================================
echo.

cd /d "%~dp0firmware"

echo Activating ESP-IDF environment...
call C:\Espressif\frameworks\esp-idf-v5.4.4\export.bat

echo Flashing ESP32 on COM4 and starting serial monitor...
idf.py -p COM4 flash monitor

pause
