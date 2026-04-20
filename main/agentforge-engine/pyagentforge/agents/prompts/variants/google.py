"""Multimodal protocol prompt variants."""

from pyagentforge.agents.prompts.registry import register_prompt_variant, PromptVariant


def register_google_variants() -> None:
    """注册 multimodal 协议提示词变体。"""
    register_prompt_variant(
        PromptVariant(
            name="google_concise",
            description="简洁输出风格，适合轻量快速响应",
            template_path="google/concise.md",
        )
    )
