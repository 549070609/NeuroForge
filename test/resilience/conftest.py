"""resilience 测试 conftest — 注入 PYTHONPATH。"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
for d in ["main", "main/agentforge-engine"]:
    p = str(root / d)
    if p not in sys.path:
        sys.path.insert(0, p)
