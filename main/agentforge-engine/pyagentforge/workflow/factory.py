"""
工作流引擎工厂

桥接 WorkflowGraph 和 AgentEngine：为每个 StepNode 创建
隔离的 AgentEngine 实例。
"""

from __future__ import annotations

from typing import Any

from pyagentforge.agents.types import get_agent_type_config
from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.checkpoint import BaseCheckpointer
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class EngineFactory:
    """为工作流节点创建 AgentEngine 实例

    每次调用 ``create()`` 都返回一个 **全新的隔离引擎**：
    独立 ContextManager、按需过滤的 ToolRegistry。
    """

    def __init__(
        self,
        provider: BaseProvider,
        base_tool_registry: ToolRegistry,
        plugin_manager: Any = None,
        checkpointer: BaseCheckpointer | None = None,
    ) -> None:
        self.provider = provider
        self.base_tools = base_tool_registry
        self.plugin_manager = plugin_manager
        self.checkpointer = checkpointer

    def create(
        self,
        agent_type: str = "explore",
        system_prompt: str | None = None,
        tools: list[str] | str = "*",
        max_iterations: int = 20,
    ) -> AgentEngine:
        """
        创建一个隔离的 AgentEngine

        Args:
            agent_type: 代理类型 (explore/plan/code/review)
            system_prompt: 可选覆盖系统提示词
            tools: 允许的工具列表，或 "*" 表示全部
            max_iterations: 最大迭代次数

        Returns:
            配置好的 AgentEngine 实例
        """
        type_config = get_agent_type_config(agent_type)
        prompt = system_prompt or type_config["system_prompt"]

        if tools == "*":
            tool_registry = self.base_tools
        elif isinstance(tools, list):
            tool_registry = self.base_tools.filter_by_permission(tools)
        else:
            tool_registry = self.base_tools

        context = ContextManager(system_prompt=prompt)

        config = AgentConfig(
            system_prompt=prompt,
            max_iterations=max_iterations,
        )

        engine = AgentEngine(
            provider=self.provider,
            tool_registry=tool_registry,
            config=config,
            context=context,
            plugin_manager=self.plugin_manager,
            checkpointer=self.checkpointer,
        )

        logger.debug(
            f"Created engine for workflow node: agent_type={agent_type}, "
            f"tools={'*' if tools == '*' else len(tools) if isinstance(tools, list) else tools}"
        )
        return engine
