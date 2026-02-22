"""
MateAgent 工具注册表

管理所有 MateAgent 工具的注册和访问。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from main.Agent.core import AgentDirectory, PlanFileManager
    from .templates import TemplateLoader

from .base import MateAgentTool

logger = logging.getLogger(__name__)


class MateAgentToolRegistry:
    """
    MateAgent 工具注册表

    管理所有工具的注册、访问和转换。

    Usage:
        registry = MateAgentToolRegistry()
        tool = registry.get("create_agent")
        tools = registry.get_all()
        anthropic_tools = registry.to_anthropic_tools()
    """

    def __init__(
        self,
        agent_directory: "AgentDirectory | None" = None,
        plan_manager: "PlanFileManager | None" = None,
        template_loader: "TemplateLoader | None" = None,
    ):
        """
        初始化工具注册表

        Args:
            agent_directory: Agent 目录实例
            plan_manager: 计划管理器实例
            template_loader: 模板加载器实例
        """
        self._directory = agent_directory
        self._plan_manager = plan_manager
        self._template_loader = template_loader
        self._tools: dict[str, MateAgentTool] = {}
        self._initialize_tools()

    def _initialize_tools(self) -> None:
        """初始化所有工具"""
        # CRUD 工具
        from .crud.create_agent import CreateAgentTool
        from .crud.modify_agent import ModifyAgentTool
        from .crud.delete_agent import DeleteAgentTool
        from .crud.list_agents import ListAgentsTool

        # 分析工具
        from .analysis.validate_agent import ValidateAgentTool
        from .analysis.analyze_requirements import AnalyzeRequirementsTool
        from .analysis.check_dependencies import CheckDependenciesTool

        # 配置工具
        from .config.render_template import RenderTemplateTool
        from .config.edit_config import EditConfigTool
        from .config.write_prompt import WritePromptTool

        # 系统工具
        from .system.spawn_subagent import SpawnSubagentTool

        # 注册所有工具
        tool_classes = [
            # CRUD
            CreateAgentTool,
            ModifyAgentTool,
            DeleteAgentTool,
            ListAgentsTool,
            # Analysis
            ValidateAgentTool,
            AnalyzeRequirementsTool,
            CheckDependenciesTool,
            # Config
            RenderTemplateTool,
            EditConfigTool,
            WritePromptTool,
            # System
            SpawnSubagentTool,
        ]

        for tool_class in tool_classes:
            tool = tool_class(
                agent_directory=self._directory,
                template_loader=self._template_loader,
            )
            self._tools[tool.name] = tool
            logger.debug(f"Registered tool: {tool.name}")

        logger.info(f"Initialized {len(self._tools)} MateAgent tools")

    def get(self, name: str) -> MateAgentTool | None:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            工具实例或 None
        """
        return self._tools.get(name)

    def get_all(self) -> dict[str, MateAgentTool]:
        """
        获取所有工具

        Returns:
            工具名称到工具实例的映射
        """
        return self._tools.copy()

    def get_by_category(self, category: str) -> list[MateAgentTool]:
        """
        按分类获取工具

        Args:
            category: 工具分类

        Returns:
            该分类下的工具列表
        """
        return [
            tool for tool in self._tools.values()
            if tool.category == category
        ]

    def to_anthropic_tools(self) -> list[dict[str, Any]]:
        """
        转换为 Anthropic 工具格式

        Returns:
            Anthropic tools 数组
        """
        return [tool.to_anthropic_schema() for tool in self._tools.values()]

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """
        转换为 OpenAI 工具格式

        Returns:
            OpenAI tools 数组
        """
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        """
        获取所有工具名称

        Returns:
            工具名称列表
        """
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# 全局注册表实例
_registry: MateAgentToolRegistry | None = None


def get_tool_registry(
    agent_directory: "AgentDirectory | None" = None,
    plan_manager: "PlanFileManager | None" = None,
    template_loader: "TemplateLoader | None" = None,
    force_new: bool = False,
) -> MateAgentToolRegistry:
    """
    获取工具注册表实例

    Args:
        agent_directory: Agent 目录实例
        plan_manager: 计划管理器实例
        template_loader: 模板加载器实例
        force_new: 是否强制创建新实例

    Returns:
        MateAgentToolRegistry 实例
    """
    global _registry
    if _registry is None or force_new:
        _registry = MateAgentToolRegistry(
            agent_directory=agent_directory,
            plan_manager=plan_manager,
            template_loader=template_loader,
        )
    return _registry
