"""确保 pyagentforge 在仓库根目录测试中可被 import。"""

from __future__ import annotations

import sys
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[2] / "main" / "agentforge-engine"
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))
