@echo off
REM Meshtastic Batch Simulator - Multiple Scenarios
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

REM Run the batch simulator
echo.
echo ========================================
echo Starting Batch Simulator...
echo ========================================
echo.
echo This will run multiple simulation scenarios
echo with different network configurations.
echo.
echo Parameters configured in batchSim.py:
echo   - Router types: MANAGED_FLOOD
echo   - Repetitions: 3
echo   - Node counts: 3, 5, 10, 15, 30
echo.
echo ========================================
echo.

call .venv\Scripts\python.exe batchSim.py

if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo ERROR: Batch simulator crashed!
    echo ========================================
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================
echo Batch simulator completed successfully
echo ========================================
echo.
pause
