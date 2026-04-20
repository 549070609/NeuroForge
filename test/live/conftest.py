"""
Pytest 配置：真实大模型（MiniMax）活体测试

- 通过环境变量 MINIMAX_API_KEY 或 MINIMAX_TOKEN_PLAN_KEY 注入密钥
- 默认端点为 MiniMax 中国区 Token Plan OpenAI 兼容接口：https://api.minimaxi.com/v1
- 默认模型为 MiniMax-M2
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 将 agentforge-engine 源码目录加入 sys.path，避免强依赖 editable 安装
_ENGINE_SRC = Path(__file__).resolve().parents[2] / "main" / "agentforge-engine"
if _ENGINE_SRC.exists() and str(_ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(_ENGINE_SRC))

from pyagentforge import LLMClient, ModelConfig, get_registry, register_model


MINIMAX_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MINIMAX_MODEL_ID = os.environ.get("MINIMAX_MODEL_ID", "MiniMax-M2")
MINIMAX_API_KEY_ENV = "MINIMAX_API_KEY"


def has_minimax_key() -> bool:
    """判断当前环境是否具备 MiniMax 真实凭据"""
    return bool(os.environ.get(MINIMAX_API_KEY_ENV))


@pytest.fixture(scope="session", autouse=True)
def register_minimax_model():
    """会话级注册 MiniMax 模型到 ModelRegistry"""
    if not has_minimax_key():
        pytest.skip(
            f"需要环境变量 {MINIMAX_API_KEY_ENV} 才能运行 MiniMax 活体测试",
            allow_module_level=False,
        )

    config = ModelConfig(
        id=MINIMAX_MODEL_ID,
        name=f"MiniMax {MINIMAX_MODEL_ID}",
        provider="minimax",
        api_type="openai-completions",
        model_name=MINIMAX_MODEL_ID,
        base_url=MINIMAX_BASE_URL,
        api_key_env=MINIMAX_API_KEY_ENV,
        supports_tools=True,
        supports_streaming=True,
        context_window=200_000,
        max_output_tokens=4096,
        timeout=120,
    )
    register_model(config, aliases=["minimax-m2", "minimax"])
    yield config
    # 会话结束时清理，避免污染其他测试
    get_registry().unregister_model(MINIMAX_MODEL_ID)


@pytest.fixture(scope="session")
def llm_client(register_minimax_model) -> LLMClient:
    """会话级共享 LLMClient

    受益于 P2 的跨 loop 安全缓存：内部按 ``(id(loop), timeout)`` 缓存 httpx client，
    pytest-asyncio 为每个用例新建 event loop 时会自动生成新的连接池并清理旧条目，
    不会再触发 ``Event loop is closed``。
    """
    return LLMClient(registry=get_registry())


@pytest.fixture(scope="session")
def minimax_model_id() -> str:
    return MINIMAX_MODEL_ID
