"""
提示词适配模块

提供模型特定的提示词变体和能力感知的提示词适配功能
"""

from pyagentforge.prompts.base import (
    PromptVariantType,
    PromptVariant,
    CapabilityModule,
    AdaptationContext,
)
from pyagentforge.prompts.registry import (
    PromptTemplateRegistry,
    get_prompt_registry,
)
from pyagentforge.prompts.adapter import (
    PromptAdapterManager,
    get_prompt_adapter,
)

__all__ = [
    # 类型定义
    "PromptVariantType",
    "PromptVariant",
    "CapabilityModule",
    "AdaptationContext",
    # 注册表
    "PromptTemplateRegistry",
    "get_prompt_registry",
    # 适配器
    "PromptAdapterManager",
    "get_prompt_adapter",
]
