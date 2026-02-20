"""
提示词模板注册表

管理提示词变体和能力模块的注册与选择
"""

import logging
from pathlib import Path
from typing import Any

from pyagentforge.prompts.base import (
    CapabilityModule,
    CapabilityType,
    ModelConfig,
    PromptVariant,
)

logger = logging.getLogger(__name__)


class PromptTemplateRegistry:
    """提示词模板注册表"""

    def __init__(self, template_dir: Path | None = None):
        """
        初始化注册表

        Args:
            template_dir: 模板文件根目录，默认为 pyagentforge/templates/prompts/
        """
        self._variants: list[PromptVariant] = []
        self._capabilities: dict[CapabilityType, CapabilityModule] = {}
        self._template_cache: dict[str, str] = {}

        if template_dir is None:
            # 默认模板目录
            template_dir = (
                Path(__file__).parent.parent / "templates" / "prompts"
            )

        self.template_dir = template_dir
        logger.info(f"Initialized PromptTemplateRegistry with template_dir={template_dir}")

    def register_variant(self, variant: PromptVariant) -> None:
        """
        注册提示词变体

        Args:
            variant: 提示词变体
        """
        self._variants.append(variant)
        self._variants.sort(key=lambda v: v.priority, reverse=True)
        logger.info(
            f"Registered prompt variant: {variant.name} (priority={variant.priority})"
        )

    def register_capability(self, module: CapabilityModule) -> None:
        """
        注册能力模块

        Args:
            module: 能力模块
        """
        self._capabilities[module.capability] = module
        logger.info(f"Registered capability module: {module.capability}")

    def select_variant(self, model_id: str, model_config: ModelConfig) -> PromptVariant | None:
        """
        根据模型选择最匹配的变体

        Args:
            model_id: 模型 ID
            model_config: 模型配置

        Returns:
            最匹配的变体，如果没有匹配则返回 None
        """
        for variant in self._variants:
            try:
                if variant.applies_to(model_id, model_config):
                    logger.info(
                        f"Selected prompt variant: {variant.name} for model={model_id}"
                    )
                    return variant
            except Exception as e:
                logger.warning(
                    f"Error checking variant {variant.name}: {e}"
                )
                continue

        logger.info(f"No matching variant found for model={model_id}")
        return None

    def get_capability_modules(self, model_config: ModelConfig) -> list[CapabilityModule]:
        """
        获取适用于给定模型配置的所有能力模块

        Args:
            model_config: 模型配置

        Returns:
            能力模块列表（按优先级降序排列）
        """
        modules = []
        for module in self._capabilities.values():
            try:
                if module.condition(model_config):
                    modules.append(module)
            except Exception as e:
                logger.warning(
                    f"Error checking capability {module.capability}: {e}"
                )
                continue

        modules.sort(key=lambda m: m.priority, reverse=True)
        return modules

    def load_template(self, template_path: str) -> str:
        """
        加载模板文件

        Args:
            template_path: 模板文件路径（相对于 templates/prompts/）

        Returns:
            模板内容

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        # 检查缓存
        if template_path in self._template_cache:
            return self._template_cache[template_path]

        # 加载文件
        full_path = self.template_dir / template_path
        if not full_path.exists():
            raise FileNotFoundError(f"Template not found: {full_path}")

        content = full_path.read_text(encoding="utf-8")

        # 缓存
        self._template_cache[template_path] = content
        logger.debug(f"Loaded template: {template_path}")

        return content

    def clear_cache(self) -> None:
        """清空模板缓存"""
        self._template_cache.clear()
        logger.info("Cleared template cache")


# 全局单例
_registry_instance: PromptTemplateRegistry | None = None


def get_prompt_registry() -> PromptTemplateRegistry:
    """
    获取全局提示词注册表单例

    Returns:
        PromptTemplateRegistry 实例
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = PromptTemplateRegistry()

        # 注册内置变体和能力模块
        _register_builtin_variants(_registry_instance)
        _register_builtin_capabilities(_registry_instance)

    return _registry_instance


def _register_builtin_variants(registry: PromptTemplateRegistry) -> None:
    """注册内置的提示词变体"""
    from pyagentforge.prompts.variants import (
        register_anthropic_variants,
        register_google_variants,
        register_openai_variants,
        register_default_variant,
    )

    register_anthropic_variants(registry)
    register_google_variants(registry)
    register_openai_variants(registry)
    register_default_variant(registry)


def _register_builtin_capabilities(registry: PromptTemplateRegistry) -> None:
    """注册内置的能力模块"""
    from pyagentforge.prompts.capabilities import register_builtin_capabilities

    register_builtin_capabilities(registry)
