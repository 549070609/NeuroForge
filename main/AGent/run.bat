@echo off
REM Auto-detect Python and Run CLI

echo.
echo ========================================
echo   Novel Writing Agent System
echo ========================================
echo.

REM Try different Python commands
set PYTHON_CMD=

REM Try python3
python3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python3
    goto :found
)

REM Try python
python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :found
)

REM Try py launcher
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :found
)

REM Try common paths
if exist "C:\Python311\python.exe" (
    set PYTHON_CMD=C:\Python311\python.exe
    goto :found
)

if exist "C:\Python310\python.exe" (
    set PYTHON_CMD=C:\Python310\python.exe
    goto :found
)

if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe
    goto :found
)

if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe" (
    set PYTHON_CMD=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310\python.exe
    goto :found
)

REM Not found
echo [ERROR] Python not found!
echo.
echo Please do ONE of the following:
echo.
echo 1. Install Python from: https://www.python.org/downloads/
echo    (Make sure to check "Add Python to PATH" during installation)
echo.
echo 2. Or find your Python installation and run:
echo    "C:\Path\To\Python\python.exe" cli.py
echo.
pause
exit /b 1

:found
echo Found Python: %PYTHON_CMD%
echo.
%PYTHON_CMD% cli.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to run CLI
    echo.
    echo Please check:
    echo 1. PyAgentForge is installed:
    echo    cd ..\pyagentforge
    echo    %PYTHON_CMD% -m pip install -e .
    echo.
    pause
)
