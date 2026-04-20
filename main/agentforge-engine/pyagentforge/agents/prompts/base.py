"""
提示词适配系统基础类型定义
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from pyagentforge.kernel.model_registry import ModelConfig


class PromptVariantType(str, Enum):
    """提示词变体类型"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    DEFAULT = "default"


class CapabilityType(str, Enum):
    """能力类型"""

    VISION = "vision"
    PARALLEL_TOOLS = "parallel_tools"
    STREAMING = "streaming"
    EXTENDED_THINKING = "extended_thinking"


@dataclass
class PromptVariant:
    """
    提示词变体

    定义针对特定模型或提供商的提示词模板
    """

    name: str
    """变体名称"""

    applies_to: Callable[[str, ModelConfig], bool]
    """判断是否适用于给定模型 (model_id, model_config) -> bool"""

    template_path: str
    """模板文件路径（相对于 templates/prompts/）"""

    priority: int = 50
    """优先级（数值越大优先级越高）"""

    description: str = ""
    """描述信息"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""


@dataclass
class CapabilityModule:
    """
    能力模块

    根据模型能力动态添加的提示词片段
    """

    capability: CapabilityType
    """能力类型"""

    condition: Callable[[ModelConfig], bool]
    """判断是否应该应用此模块"""

    template_section: str
    """提示词片段内容"""

    priority: int = 50
    """优先级（数值越大越先应用）"""

    description: str = ""
    """描述信息"""


@dataclass
class AdaptationContext:
    """
    提示词适配上下文

    包含适配所需的所有信息
    """

    model_id: str
    """模型 ID"""

    model_config: ModelConfig
    """模型配置"""

    base_prompt: str
    """基础系统提示词"""

    available_tools: list[dict[str, Any]] = field(default_factory=list)
    """可用工具列表"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """额外上下文信息"""
