"""
思考级别控制模块

支持不同深度的推理模式，适配各模型的 extended thinking 能力
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel


class ThinkingLevel(str, Enum):
    """思考级别枚举"""

    OFF = "off"  # 关闭扩展思考
    MINIMAL = "minimal"  # 最小思考
    LOW = "low"  # 低思考
    MEDIUM = "medium"  # 中等思考
    HIGH = "high"  # 高思考
    XHIGH = "xhigh"  # 超高思考

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
            raise ValueError(
                f"Invalid thinking level: {value}. "
                f"Valid values: {list(mapping.keys())}"
            )
        return mapping[value]


class ThinkingConfig(BaseModel):
    """思考配置"""

    level: ThinkingLevel = ThinkingLevel.OFF
    budget_tokens: int | None = None  # 思考 token 预算（用于 Claude）

    # 模型特定的思考参数
    anthropic_thinking: dict[str, Any] | None = None
    openai_reasoning_effort: str | None = None
    google_thinking_budget: int | None = None

    def is_enabled(self) -> bool:
        """是否启用思考"""
        return self.level != ThinkingLevel.OFF

    def to_anthropic_params(self) -> dict[str, Any]:
        """
        转换为 Anthropic API 参数

        Anthropic 使用 thinking 参数控制扩展思考
        """
        if not self.is_enabled():
            return {}

        # 计算思考预算
        budget = self.budget_tokens or self._calculate_budget()

        params: dict[str, Any] = {}

        # Anthropic 的 thinking 配置
        if self.anthropic_thinking:
            params["thinking"] = self.anthropic_thinking
        else:
            # 根据级别计算配置
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": budget,
            }

        return params

    def to_openai_params(self) -> dict[str, Any]:
        """
        转换为 OpenAI API 参数

        OpenAI 使用 reasoning_effort 参数
        """
        if not self.is_enabled():
            return {}

        params: dict[str, Any] = {}

        if self.openai_reasoning_effort:
            params["reasoning_effort"] = self.openai_reasoning_effort
        else:
            # 映射到 OpenAI 的 effort 级别
            effort_mapping = {
                ThinkingLevel.MINIMAL: "low",
                ThinkingLevel.LOW: "low",
                ThinkingLevel.MEDIUM: "medium",
                ThinkingLevel.HIGH: "high",
                ThinkingLevel.XHIGH: "high",
            }
            params["reasoning_effort"] = effort_mapping.get(
                self.level, "medium"
            )

        return params

    def to_google_params(self) -> dict[str, Any]:
        """
        转换为 Google Generative AI 参数

        Google 使用 thinkingBudget 配置
        """
        if not self.is_enabled():
            return {}

        params: dict[str, Any] = {}

        if self.google_thinking_budget:
            params["thinkingBudget"] = self.google_thinking_budget
        else:
            # 根据级别计算预算
            params["thinkingBudget"] = self._calculate_budget()

        return params

    def _calculate_budget(self) -> int:
        """根据思考级别计算 token 预算"""
        budget_mapping = {
            ThinkingLevel.OFF: 0,
            ThinkingLevel.MINIMAL: 1024,
            ThinkingLevel.LOW: 2048,
            ThinkingLevel.MEDIUM: 4096,
            ThinkingLevel.HIGH: 8192,
            ThinkingLevel.XHIGH: 16000,
        }
        return budget_mapping.get(self.level, 4096)


# 支持思考的模型列表
THINKING_CAPABLE_MODELS = {
    # Anthropic Claude 模型
    "claude-3-5-sonnet": {
        "provider": "anthropic",
        "max_thinking_tokens": 16000,
    },
    "claude-3-5-haiku": {
        "provider": "anthropic",
        "max_thinking_tokens": 8000,
    },
    "claude-sonnet-4": {
        "provider": "anthropic",
        "max_thinking_tokens": 16000,
    },
    "claude-opus-4": {
        "provider": "anthropic",
        "max_thinking_tokens": 32000,
    },
    # OpenAI o 系列模型
    "o1-preview": {
        "provider": "openai",
        "max_thinking_tokens": 32000,
    },
    "o1-mini": {
        "provider": "openai",
        "max_thinking_tokens": 16000,
    },
    "o3-mini": {
        "provider": "openai",
        "max_thinking_tokens": 16000,
    },
    # Google Gemini 模型
    "gemini-2.0-flash-thinking": {
        "provider": "google",
        "max_thinking_tokens": 24000,
    },
}


def supports_thinking(model_id: str) -> bool:
    """
    检查模型是否支持扩展思考

    Args:
        model_id: 模型 ID

    Returns:
        是否支持思考
    """
    model_lower = model_id.lower()
    for pattern in THINKING_CAPABLE_MODELS:
        if pattern in model_lower:
            return True
    return False


def get_thinking_provider(model_id: str) -> str | None:
    """
    获取模型的思考功能提供商

    Args:
        model_id: 模型 ID

    Returns:
        提供商名称 (anthropic/openai/google) 或 None
    """
    model_lower = model_id.lower()
    for pattern, config in THINKING_CAPABLE_MODELS.items():
        if pattern in model_lower:
            return config["provider"]
    return None


def get_max_thinking_tokens(model_id: str) -> int:
    """
    获取模型的最大思考 token 数

    Args:
        model_id: 模型 ID

    Returns:
        最大思考 tokens
    """
    model_lower = model_id.lower()
    for pattern, config in THINKING_CAPABLE_MODELS.items():
        if pattern in model_lower:
            return config["max_thinking_tokens"]
    return 4096  # 默认值


def create_thinking_config(
    level: ThinkingLevel | str,
    model_id: str | None = None,
    budget_tokens: int | None = None,
) -> ThinkingConfig:
    """
    创建思考配置

    Args:
        level: 思考级别
        model_id: 模型 ID（用于自动调整预算）
        budget_tokens: 指定的 token 预算

    Returns:
        思考配置
    """
    if isinstance(level, str):
        level = ThinkingLevel.parse(level)

    config = ThinkingConfig(level=level)

    # 如果指定了预算，使用指定值
    if budget_tokens:
        config.budget_tokens = budget_tokens
    # 否则根据模型自动调整
    elif model_id:
        max_tokens = get_max_thinking_tokens(model_id)
        # 根据级别使用不同比例
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


# ThinkingBlock 已迁移至 kernel/message.py（避免循环导入），此处重导出保持兼容
from pyagentforge.kernel.message import ThinkingBlock  # noqa: E402, F401
