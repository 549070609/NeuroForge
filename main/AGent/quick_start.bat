@echo off
REM Quick Start Script - More Robust Launcher

echo.
echo Starting Novel Writing Agent System...
echo.

python quick_start.py

if errorlevel 1 (
    echo.
    echo If you see import errors, please run:
    echo   cd ..\pyagentforge
    echo   pip install -e .
    echo.
)

pause
