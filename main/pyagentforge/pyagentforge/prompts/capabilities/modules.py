"""
能力模块定义

根据模型能力动态添加提示词片段
"""

from pyagentforge.prompts.base import CapabilityModule, CapabilityType
from pyagentforge.prompts.registry import PromptTemplateRegistry


def register_builtin_capabilities(registry: PromptTemplateRegistry) -> None:
    """注册内置能力模块"""

    # 视觉能力
    register_vision_capability(registry)

    # 并行工具调用能力
    register_parallel_tools_capability(registry)


def register_vision_capability(registry: PromptTemplateRegistry) -> None:
    """注册视觉能力模块"""

    registry.register_capability(
        CapabilityModule(
            capability=CapabilityType.VISION,
            condition=lambda cfg: cfg.supports_vision,
            template_section="""## 图像处理能力

你可以处理和分析图像输入。当用户提供图像时：
- 仔细观察图像内容
- 描述图像中的关键信息
- 根据用户需求分析图像
- 提供基于图像的准确回答""",
            priority=60,
            description="视觉处理能力",
        )
    )


def register_parallel_tools_capability(registry: PromptTemplateRegistry) -> None:
    """注册并行工具调用能力模块"""

    # 假设大多数现代模型支持并行工具调用
    registry.register_capability(
        CapabilityModule(
            capability=CapabilityType.PARALLEL_TOOLS,
            condition=lambda cfg: True,  # 默认启用
            template_section="""## 并行工具调用

你可以同时调用多个独立的工具来提高效率。当需要执行多个不相互依赖的操作时：
- 识别哪些操作可以并行执行
- 在单次响应中调用所有独立工具
- 避免等待不必要的中间结果

注意：只有相互独立的操作才能并行调用。""",
            priority=50,
            description="并行工具调用能力",
        )
    )
