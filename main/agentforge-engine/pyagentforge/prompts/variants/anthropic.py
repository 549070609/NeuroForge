"""
Anthropic 模型提示词变体
"""

from pyagentforge.kernel.model_registry import ModelConfig, ProviderType
from pyagentforge.prompts.base import PromptVariant
from pyagentforge.prompts.registry import PromptTemplateRegistry


def register_anthropic_variants(registry: PromptTemplateRegistry) -> None:
    """注册 Anthropic 模型变体"""

    # Extended Thinking 变体 - 仅适用于 Claude Sonnet 4 和 Opus 4
    registry.register_variant(
        PromptVariant(
            name="anthropic_extended_thinking",
            applies_to=lambda mid, cfg: (
                cfg.provider == ProviderType.ANTHROPIC
                and any(x in mid.lower() for x in ["claude-sonnet-4", "claude-opus-4"])
            ),
            template_path="anthropic/extended_thinking.md",
            priority=100,
            description="Extended Thinking 模式，适用于 Claude Sonnet 4 和 Opus 4",
        )
    )

    # 标准 Anthropic 变体 - 适用于所有 Claude 模型
    registry.register_variant(
        PromptVariant(
            name="anthropic_standard",
            applies_to=lambda mid, cfg: cfg.provider == ProviderType.ANTHROPIC,
            template_path="anthropic/standard.md",
            priority=50,
            description="标准 Anthropic 提示词模板",
        )
    )
