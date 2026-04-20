"""
默认提示词变体
"""

from pyagentforge.agents.prompts.base import PromptVariant
from pyagentforge.agents.prompts.registry import PromptTemplateRegistry


def register_default_variant(registry: PromptTemplateRegistry) -> None:
    """注册默认变体"""

    registry.register_variant(
        PromptVariant(
            name="default",
            applies_to=lambda mid, cfg: True,  # 匹配所有模型
            template_path="base.md",
            priority=10,  # 最低优先级
            description="默认提示词模板",
        )
    )
