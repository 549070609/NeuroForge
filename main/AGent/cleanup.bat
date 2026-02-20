@echo off
chcp 65001 >nul
echo 正在清理 AGent 目录的无效文件...
echo.

echo [1/3] 删除冗余脚本...
del /f /q "find_python.bat" 2>nul && echo   ✓ find_python.bat
del /f /q "run_py.bat" 2>nul && echo   ✓ run_py.bat
del /f /q "diagnose.py" 2>nul && echo   ✓ diagnose.py
del /f /q "test_imports.py" 2>nul && echo   ✓ test_imports.py
del /f /q "verify.py" 2>nul && echo   ✓ verify.py
del /f /q "test_debug.py" 2>nul && echo   ✓ test_debug.py
del /f /q "cli_real.py" 2>nul && echo   ✓ cli_real.py
del /f /q "cli_glm.py" 2>nul && echo   ✓ cli_glm.py

echo.
echo [2/3] 删除临时文档...
del /f /q "DEBUG_GUIDE.md" 2>nul && echo   ✓ DEBUG_GUIDE.md

echo.
echo [3/3] 删除 Python 缓存...
if exist "__pycache__" (
    rmdir /s /q "__pycache__"
    echo   ✓ __pycache__
)
if exist "agents\__pycache__" (
    rmdir /s /q "agents\__pycache__"
    echo   ✓ agents\__pycache__
)

echo.
echo ============================================================
echo   清理完成！
echo ============================================================
echo.
echo 保留的核心文件：
echo   - cli.py (主 CLI)
echo   - builder_demo.py, loader_demo.py, workflow_demo.py (演示)
echo   - start.bat, quick_start.bat, test_basic.bat (启动脚本)
echo   - README.md, CLI使用指南.md, 实现总结.md (文档)
echo   - setup_glm.py, README_GLM.md (GLM 集成)
echo.
pause
