"""test/service conftest — sys.path 注入"""

import sys
from pathlib import Path

# main 目录：使 Service 包的相对导入正常工作
MAIN_ROOT = Path(__file__).resolve().parents[2] / "main"
if str(MAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(MAIN_ROOT))

# agentforge-engine：使 pyagentforge 可导入
ENGINE_ROOT = Path(__file__).resolve().parents[2] / "main" / "agentforge-engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))
