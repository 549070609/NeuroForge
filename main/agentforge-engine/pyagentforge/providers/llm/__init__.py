"""
国产大模型 LLM Provider 模块

提供统一的国产大模型适配层，支持:
- 智谱 GLM 系列
- 阿里 Qwen 系列 (扩展)
- 深度求索 DeepSeek 系列 (扩展)
"""

from pyagentforge.providers.llm.glm import GLMEndpoint, GLMProvider
from pyagentforge.providers.llm.registry import (
    ChineseLLMInfo,
    ChineseLLMRegistry,
    register_chinese_llm,
)

__all__ = [
    # GLM
    "GLMProvider",
    "GLMEndpoint",
    # Registry
    "ChineseLLMRegistry",
    "ChineseLLMInfo",
    "register_chinese_llm",
]
