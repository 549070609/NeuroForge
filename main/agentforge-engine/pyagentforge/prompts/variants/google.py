"""
Google 模型提示词变体
"""

from pyagentforge.kernel.model_registry import ModelConfig, ProviderType
from pyagentforge.prompts.base import PromptVariant
from pyagentforge.prompts.registry import PromptTemplateRegistry


def register_google_variants(registry: PromptTemplateRegistry) -> None:
    """注册 Google 模型变体"""

    registry.register_variant(
        PromptVariant(
            name="google_concise",
            applies_to=lambda mid, cfg: cfg.provider == ProviderType.GOOGLE,
            template_path="google/concise.md",
            priority=50,
            description="简洁输出风格，适合 Gemini",
        )
    )
