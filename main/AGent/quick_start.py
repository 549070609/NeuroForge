#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速启动脚本 - 诊断版本
"""

import sys
import os
from pathlib import Path

# 添加 pyagentforge 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "main" / "pyagentforge"))

print("="*60)
print("  Novel Writing Agent System - Quick Start")
print("="*60)
print()

# 检查 Python 版本
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print()

# 尝试导入
try:
    print("Checking imports...")
    from pyagentforge.building import AgentBuilder
    print("  ✓ AgentBuilder imported")
except Exception as e:
    print(f"  ✗ Failed to import AgentBuilder: {e}")
    print()
    print("Please install PyAgentForge first:")
    print("  cd ..\\pyagentforge")
    print("  pip install -e .")
    print()
    input("Press Enter to exit...")
    sys.exit(1)

print()
print("All checks passed! Starting CLI...")
print()

# 导入并运行 CLI
try:
    import cli
    cli.main()
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
    print()
    input("Press Enter to exit...")
    sys.exit(1)
