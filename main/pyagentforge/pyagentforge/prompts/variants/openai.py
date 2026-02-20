"""
OpenAI 模型提示词变体
"""

from pyagentforge.kernel.model_registry import ModelConfig, ProviderType
from pyagentforge.prompts.base import PromptVariant
from pyagentforge.prompts.registry import PromptTemplateRegistry


def register_openai_variants(registry: PromptTemplateRegistry) -> None:
    """注册 OpenAI 模型变体"""

    registry.register_variant(
        PromptVariant(
            name="openai_autonomous",
            applies_to=lambda mid, cfg: cfg.provider == ProviderType.OPENAI,
            template_path="openai/autonomous.md",
            priority=50,
            description="自主工作流，适合 GPT 系列",
        )
    )
