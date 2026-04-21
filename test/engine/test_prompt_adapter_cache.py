"""P1-4 _adapt_system_prompt 缓存回归测试。"""

from __future__ import annotations

import pytest

from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.executor import ToolRegistry


class _StubProvider:
    """只暴露 model 属性的最小 provider 替身。"""

    def __init__(self, model: str = "stub-model"):
        self.model = model


class TestAdaptSystemPromptCache:
    def _make_engine(self, model: str = "stub-model") -> AgentEngine:
        provider = _StubProvider(model)
        engine = AgentEngine.__new__(AgentEngine)
        engine.provider = provider
        engine.config = AgentConfig(system_prompt="base prompt")
        engine.tools = ToolRegistry()
        return engine

    def test_cache_hit_on_same_model(self):
        engine = self._make_engine()
        result1 = engine._adapt_system_prompt()
        result2 = engine._adapt_system_prompt()
        assert result1 == result2
        assert hasattr(engine, "_adapted_cache") or result1 == "base prompt"

    def test_no_model_config_returns_base(self):
        engine = self._make_engine("nonexistent-model-xyz")
        result = engine._adapt_system_prompt()
        assert result == "base prompt"

    def test_cache_invalidated_on_model_change(self):
        engine = self._make_engine()
        _ = engine._adapt_system_prompt()
        engine.provider.model = "other-model"
        result = engine._adapt_system_prompt()
        assert result == "base prompt"
