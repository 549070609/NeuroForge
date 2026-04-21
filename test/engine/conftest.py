"""test/engine conftest — sys.path 注入 + 公共 fixture"""

import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[2] / "main" / "agentforge-engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

# 把 test/engine 目录加入 sys.path，使 helpers 可被 import
TEST_ENGINE_DIR = str(Path(__file__).resolve().parent)
if TEST_ENGINE_DIR not in sys.path:
    sys.path.insert(0, TEST_ENGINE_DIR)
