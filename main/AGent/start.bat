@echo off
chcp 65001 >nul
REM Novel Writing Agent System - Windows Launcher

echo.
echo ========================================
echo   Novel Writing Agent System
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Run the CLI
python cli.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo [ERROR] Program exited with errors
    pause
)
