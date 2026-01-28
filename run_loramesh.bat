@echo off
REM Meshtastic LoRa Mesh Simulator - Discrete Event
REM Author: GitHub Copilot
REM Date: 2026-01-28

setlocal enabledelayedexpansion

REM Change to script directory
cd /d "%~dp0"

REM Check if Python virtual environment exists
if not exist ".venv" (
    echo.
    echo ========================================
    echo ERROR: Virtual environment not found!
    echo ========================================
    echo.
    echo Please run this command first to create the environment:
    echo   python -m venv .venv
    echo.
    pause
    exit /b 1
)

REM Run the LoRa Mesh simulator
echo.
echo ========================================
echo Starting LoRa Mesh Discrete Event Simulator...
echo ========================================
echo.

call .venv\Scripts\python.exe loraMesh.py

if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo ERROR: Simulator crashed!
    echo ========================================
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo Simulator closed successfully
echo ========================================
echo.
pause
