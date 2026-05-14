@echo off
REM JARVIS Mark-XL Startup Launcher
REM Run this as Administrator for full file system access

cd /d "%~dp0"
title JARVIS Mark-XL

echo Starting JARVIS Mark-XL...
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+ and add to PATH.
    pause
    exit /b 1
)

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run JARVIS backend
python -m backend.main

REM If we get here, JARVIS crashed — pause for inspection
echo.
echo JARVIS has stopped. Press any key to exit...
pause >nul