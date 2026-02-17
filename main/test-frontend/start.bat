@echo off
echo ================================
echo PyAgentForge Test Environment
echo ================================
echo.

:: Check if .env exists
if not exist "..\glm-provider\.env" (
    echo [Warning] .env file not found!
    echo Please copy .env.example to .env and configure GLM_API_KEY
    echo.
    pause
    exit /b 1
)

:: Start backend
echo [1/2] Starting GLM Provider Backend...
start "GLM Backend" cmd /k "cd ..\glm-provider && python server.py"

:: Wait for backend to start
timeout /t 3 /nobreak > nul

:: Start frontend
echo [2/2] Starting Frontend...
start "Frontend" cmd /k "npm run dev"

echo.
echo ================================
echo Services started!
echo - Backend: http://localhost:8100
echo - Frontend: http://localhost:3000
echo ================================
pause
