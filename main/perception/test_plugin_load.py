"""
验证感知器插件加载

运行: cd Agent-Learn/main && python -m perception.test_plugin_load
"""

import asyncio
import sys
from pathlib import Path

# 确保 agentforge-engine 可导入
_main_dir = Path(__file__).resolve().parent.parent
if str(_main_dir) not in sys.path:
    sys.path.insert(0, str(_main_dir))

# 需安装 pyagentforge (pip install -e agentforge-engine)
try:
    from pyagentforge import create_engine
    from pyagentforge.config.plugin_config import PluginConfig
    from pyagentforge.kernel.base_provider import BaseProvider
    from pyagentforge.kernel.message import ProviderResponse, TextBlock
except ImportError as e:
    print(f"[SKIP] pyagentforge not available: {e}")
    print("Run: pip install -e agentforge-engine")
    sys.exit(0)


class _MockProvider(BaseProvider):
    """Mock provider for plugin load test (no API call)"""
    def __init__(self):
        super().__init__(model="mock")

    async def create_message(self, system, messages, tools, **kwargs):
        return ProviderResponse(
            content=[TextBlock(text="ok")],
            stop_reason="end_turn",
        )

    async def count_tokens(self, messages):
        return 0


async def test_plugin_load():
    """验证插件加载及工具注册"""
    plugins_dir = Path(__file__).resolve().parent.parent  # main/
    plugin_config = PluginConfig(
        preset="minimal",
        enabled=["integration.perception"],
        plugin_dirs=[str(plugins_dir)],
        config={
            "integration.perception": {
                "log_path": "./logs",
                "filter_rules": {"level": ["error", "warn"]},
            }
        },
    )

    engine = await create_engine(
        provider=_MockProvider(),
        plugin_config=plugin_config,
        working_dir=str(_main_dir),
    )

    tools = engine.tools
    all_tools = tools.get_all() if hasattr(tools, "get_all") else {}
    tool_names = list(all_tools.keys()) if isinstance(all_tools, dict) else []

    perception_tools = ["parse_log", "perceive", "read_logs", "execute_decision"]
    found = [t for t in perception_tools if t in tool_names]

    if len(found) == len(perception_tools):
        print(f"[OK] Perception plugin loaded, tools: {found}")
        return True
    print(f"[WARN] Expected {perception_tools}, got: {tool_names}")
    return False


if __name__ == "__main__":
    ok = asyncio.run(test_plugin_load())
    sys.exit(0 if ok else 1)
