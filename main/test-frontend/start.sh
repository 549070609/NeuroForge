#!/bin/bash

echo "================================"
echo "PyAgentForge Test Environment"
echo "================================"
echo

# Check if .env exists
if [ ! -f "../glm-provider/.env" ]; then
    echo "[Warning] .env file not found!"
    echo "Please copy .env.example to .env and configure GLM_API_KEY"
    echo
    exit 1
fi

# Start backend
echo "[1/2] Starting GLM Provider Backend..."
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'/../glm-provider\" && python server.py"'

# Wait for backend
sleep 3

# Start frontend
echo "[2/2] Starting Frontend..."
npm run dev

echo
echo "================================"
echo "Services started!"
echo "- Backend: http://localhost:8100"
echo "- Frontend: http://localhost:3000"
echo "================================"
