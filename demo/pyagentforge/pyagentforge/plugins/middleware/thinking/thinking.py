"""
思考级别控制模块

支持不同深度的推理模式，适配各模型的 extended thinking 能力
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel


class ThinkingLevel(str, Enum):
    """思考级别枚举"""

    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"

    @classmethod
    def parse(cls, value: str) -> "ThinkingLevel":
        """解析字符串为思考级别"""
        value = value.lower().strip()
        mapping = {
            "off": cls.OFF,
            "none": cls.OFF,
            "disabled": cls.OFF,
            "minimal": cls.MINIMAL,
            "min": cls.MINIMAL,
            "low": cls.LOW,
            "medium": cls.MEDIUM,
            "med": cls.MEDIUM,
            "high": cls.HIGH,
            "xhigh": cls.XHIGH,
            "extra_high": cls.XHIGH,
            "max": cls.XHIGH,
        }
        if value not in mapping:
            raise ValueError(f"Invalid thinking level: {value}")
        return mapping[value]


class ThinkingConfig(BaseModel):
    """思考配置"""

    level: ThinkingLevel = ThinkingLevel.OFF
    budget_tokens: int | None = None

    def is_enabled(self) -> bool:
        return self.level != ThinkingLevel.OFF

    def to_anthropic_params(self) -> dict[str, Any]:
        if not self.is_enabled():
            return {}

        budget = self.budget_tokens or self._calculate_budget()
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}

    def to_openai_params(self) -> dict[str, Any]:
        if not self.is_enabled():
            return {}

        effort_mapping = {
            ThinkingLevel.MINIMAL: "low",
            ThinkingLevel.LOW: "low",
            ThinkingLevel.MEDIUM: "medium",
            ThinkingLevel.HIGH: "high",
            ThinkingLevel.XHIGH: "high",
        }
        return {"reasoning_effort": effort_mapping.get(self.level, "medium")}

    def to_google_params(self) -> dict[str, Any]:
        if not self.is_enabled():
            return {}

        return {"thinkingBudget": self.budget_tokens or self._calculate_budget()}

    def _calculate_budget(self) -> int:
        budget_mapping = {
            ThinkingLevel.OFF: 0,
            ThinkingLevel.MINIMAL: 1024,
            ThinkingLevel.LOW: 2048,
            ThinkingLevel.MEDIUM: 4096,
            ThinkingLevel.HIGH: 8192,
            ThinkingLevel.XHIGH: 16000,
        }
        return budget_mapping.get(self.level, 4096)


THINKING_CAPABLE_MODELS = {
    "claude-3-5-sonnet": {"provider": "anthropic", "max_thinking_tokens": 16000},
    "claude-3-5-haiku": {"provider": "anthropic", "max_thinking_tokens": 8000},
    "claude-sonnet-4": {"provider": "anthropic", "max_thinking_tokens": 16000},
    "claude-opus-4": {"provider": "anthropic", "max_thinking_tokens": 32000},
    "o1-preview": {"provider": "openai", "max_thinking_tokens": 32000},
    "o1-mini": {"provider": "openai", "max_thinking_tokens": 16000},
    "o3-mini": {"provider": "openai", "max_thinking_tokens": 16000},
    "gemini-2.0-flash-thinking": {"provider": "google", "max_thinking_tokens": 24000},
}


def supports_thinking(model_id: str) -> bool:
    """检查模型是否支持扩展思考"""
    model_lower = model_id.lower()
    return any(pattern in model_lower for pattern in THINKING_CAPABLE_MODELS)


def get_max_thinking_tokens(model_id: str) -> int:
    """获取模型的最大思考 token 数"""
    model_lower = model_id.lower()
    for pattern, config in THINKING_CAPABLE_MODELS.items():
        if pattern in model_lower:
            return config["max_thinking_tokens"]
    return 4096


def create_thinking_config(
    level: ThinkingLevel | str,
    model_id: str | None = None,
    budget_tokens: int | None = None,
) -> ThinkingConfig:
    """创建思考配置"""
    if isinstance(level, str):
        level = ThinkingLevel.parse(level)

    config = ThinkingConfig(level=level)

    if budget_tokens:
        config.budget_tokens = budget_tokens
    elif model_id:
        max_tokens = get_max_thinking_tokens(model_id)
        ratio_mapping = {
            ThinkingLevel.MINIMAL: 0.1,
            ThinkingLevel.LOW: 0.2,
            ThinkingLevel.MEDIUM: 0.4,
            ThinkingLevel.HIGH: 0.7,
            ThinkingLevel.XHIGH: 1.0,
        }
        ratio = ratio_mapping.get(level, 0.4)
        config.budget_tokens = int(max_tokens * ratio)

    return config


class ThinkingBlock(BaseModel):
    """思考内容块"""

    type: Literal["thinking"] = "thinking"
    thinking: str
    signature: str | None = None
