"""
LLM 提供商模块

包含提供商基类和各种 LLM 提供商实现
"""

from pyagentforge.providers.base import BaseProvider
from pyagentforge.kernel.message import ProviderResponse
from pyagentforge.providers.anthropic_provider import AnthropicProvider
from pyagentforge.providers.openai_provider import OpenAIProvider
from pyagentforge.providers.google_provider import GoogleProvider
from pyagentforge.providers.factory import (
    ModelAdapterFactory,
    create_provider,
    get_factory,
    get_supported_models,
)

# 延迟导入 Chinese LLM 模块以避免循环导入
def __getattr__(name: str):
    """延迟导入 Chinese LLM 相关类"""
    if name in ("GLMProvider", "GLMEndpoint"):
        from pyagentforge.providers.llm.glm import GLMProvider, GLMEndpoint

        if name == "GLMProvider":
            return GLMProvider
        return GLMEndpoint
    elif name in ("ChineseLLMRegistry", "ChineseLLMInfo", "register_chinese_llm"):
        from pyagentforge.providers.llm.registry import (
            ChineseLLMRegistry,
            ChineseLLMInfo,
            register_chinese_llm,
        )

        if name == "ChineseLLMRegistry":
            return ChineseLLMRegistry
        elif name == "ChineseLLMInfo":
            return ChineseLLMInfo
        return register_chinese_llm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base
    "BaseProvider",
    "ProviderResponse",
    # Providers
    "AnthropicProvider",
    "OpenAIProvider",
    "GoogleProvider",
    # Chinese LLM
    "GLMProvider",
    "GLMEndpoint",
    "ChineseLLMRegistry",
    "ChineseLLMInfo",
    "register_chinese_llm",
    # Factory
    "ModelAdapterFactory",
    "create_provider",
    "get_factory",
    "get_supported_models",
]
