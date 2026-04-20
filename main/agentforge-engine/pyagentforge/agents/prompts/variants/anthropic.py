"""Messages protocol prompt variants."""

from pyagentforge.agents.prompts.registry import register_prompt_variant, PromptVariant


def register_anthropic_variants() -> None:
    """注册 messages 协议提示词变体。"""
    register_prompt_variant(
        PromptVariant(
            name="anthropic_extended_thinking",
            description="Extended Thinking 模式，适用于高推理深度场景",
            template_path="anthropic/extended_thinking.md",
        )
    )
    register_prompt_variant(
        PromptVariant(
            name="anthropic_standard",
            description="标准 messages 协议提示词模板",
            template_path="anthropic/standard.md",
        )
    )
