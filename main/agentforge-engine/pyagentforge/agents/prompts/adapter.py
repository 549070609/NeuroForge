"""
提示词适配管理器

根据模型配置自动适配系统提示词
"""

import logging
from typing import Any

from pyagentforge.agents.prompts.base import AdaptationContext, CapabilityModule, PromptVariant
from pyagentforge.agents.prompts.registry import get_prompt_registry

logger = logging.getLogger(__name__)


class PromptAdapterManager:
    """提示词适配管理器"""

    def __init__(self):
        """初始化适配管理器"""
        self.registry = get_prompt_registry()

    def adapt_prompt(self, context: AdaptationContext) -> str:
        """
        适配系统提示词

        流程:
        1. 选择模型变体
        2. 加载变体模板
        3. 应用能力模块
        4. 组装最终提示词

        Args:
            context: 适配上下文

        Returns:
            适配后的系统提示词
        """
        logger.info(
            f"Adapting prompt for model={context.model_id}, "
            f"base_prompt_len={len(context.base_prompt)}"
        )

        # 步骤 1: 选择变体
        variant = self.registry.select_variant(
            context.model_id, context.model_config
        )

        # 步骤 2: 加载模板
        if variant:
            try:
                template_content = self.registry.load_template(variant.template_path)
                logger.info(f"Using variant template: {variant.name}")
            except FileNotFoundError:
                logger.warning(
                    f"Template file not found: {variant.template_path}, "
                    f"falling back to base prompt"
                )
                template_content = None
        else:
            template_content = None

        # 步骤 3: 获取能力模块
        capability_modules = self.registry.get_capability_modules(context.model_config)
        logger.info(f"Found {len(capability_modules)} applicable capability modules")

        # 步骤 4: 组装最终提示词
        final_prompt = self._assemble_prompt(
            base_prompt=context.base_prompt,
            template=template_content,
            capabilities=capability_modules,
            context=context,
        )

        logger.info(f"Prompt adaptation complete, final_len={len(final_prompt)}")
        return final_prompt

    def _assemble_prompt(
        self,
        base_prompt: str,
        template: str | None,
        capabilities: list[CapabilityModule],
        context: AdaptationContext,
    ) -> str:
        """
        组装最终提示词

        优先级:
        1. 模板内容（如果存在）
        2. 基础提示词
        3. 能力模块（追加到末尾）

        Args:
            base_prompt: 基础提示词
            template: 模板内容
            capabilities: 能力模块列表
            context: 适配上下文

        Returns:
            组装后的提示词
        """
        # 使用模板或基础提示词
        if template:
            main_content = template
        else:
            main_content = base_prompt

        # 构建能力模块部分
        capability_sections = []
        for module in capabilities:
            capability_sections.append(f"\n{module.template_section}\n")

        # 组装
        if capability_sections:
            capabilities_content = "\n".join(capability_sections)
            final_prompt = f"{main_content}\n\n{capabilities_content}"
        else:
            final_prompt = main_content

        return final_prompt


# 全局单例
_adapter_instance: PromptAdapterManager | None = None


def get_prompt_adapter() -> PromptAdapterManager:
    """
    获取全局提示词适配管理器单例

    Returns:
        PromptAdapterManager 实例
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = PromptAdapterManager()
    return _adapter_instance
