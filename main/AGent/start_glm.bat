@echo off
chcp 65001 > nul
echo ============================================================
echo    AGent - GLM AI 模式启动器
echo ============================================================
echo.

cd /d "%~dp0"

echo [启动中] 正在启动 GLM AI 模式...
echo.

py cli_glm.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo [错误] 启动失败！
    echo ============================================================
    echo.
    echo 可能的原因：
    echo  1. 未配置 GLM API Key - 运行: py setup_glm.py
    echo  2. 缺少依赖 - 运行: pip install openai python-dotenv
    echo.
    pause
    exit /b 1
)
