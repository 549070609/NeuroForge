"""Chat/Responses protocol prompt variants."""

from pyagentforge.prompts.registry import register_prompt_variant, PromptVariant


def register_openai_variants() -> None:
    """注册 chat/responses 协议提示词变体。"""
    register_prompt_variant(
        PromptVariant(
            name="openai_autonomous",
            description="自主执行风格提示词模板",
            template_path="openai/autonomous.md",
        )
    )
