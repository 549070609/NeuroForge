"""
Agent Executor - Agent 执行器

集成 pyagentforge 核心功能，在工作区域上下文中执行 Agent。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Callable

# 延迟导入
# from pyagentforge.kernel.engine import AgentEngine, AgentConfig
# from pyagentforge.kernel.base_provider import BaseProvider
# from pyagentforge.tools.registry import ToolRegistry
# from pyagentforge.providers.factory import create_provider

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    output: str
    error: str | None = None
    iterations: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentExecutor:
    """
    Agent 执行器

    在工作区域上下文中执行 Agent，集成 pyagentforge 核心功能。
    """

    def __init__(self, workspace_context: Any) -> None:
        """
        初始化执行器

        Args:
            workspace_context: WorkspaceContext 实例
        """
        self._workspace_context = workspace_context
        self._provider: Any = None
        self._tool_registry: Any = None
        self._engine: Any = None
        self._config: Any = None
        self._initialized = False
        self._logger = logging.getLogger(f"{__name__}.AgentExecutor")

    async def initialize(
        self,
        agent_definition: dict[str, Any],
        system_prompt: str | None = None,
    ) -> None:
        """
        初始化执行器

        Args:
            agent_definition: Agent 定义 (来自 Agent 定义的 metadata)
            system_prompt: 系统提示词 (可选)
        """
        if self._initialized:
            self._logger.warning("Executor already initialized")
            return

        try:
            # 创建 Provider
            self._provider = self._create_provider(agent_definition)

            # 创建工具注册表
            self._tool_registry = self._create_tool_registry(agent_definition)

            # 创建 Agent 配置
            self._config = self._create_agent_config(agent_definition, system_prompt)

            # 创建 Agent 引擎
            self._engine = self._create_engine()

            self._initialized = True
            self._logger.info("AgentExecutor initialized successfully")

        except Exception as e:
            self._logger.error(f"Failed to initialize AgentExecutor: {e}")
            raise

    async def execute(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        执行 Agent

        Args:
            prompt: 用户输入
            context: 执行上下文 (可选)

        Returns:
            ExecutionResult
        """
        if not self._initialized:
            raise RuntimeError("Executor not initialized. Call initialize() first.")

        self._logger.info(f"Executing agent with prompt length: {len(prompt)}")

        try:
            # 合并上下文到提示词
            full_prompt = self._build_prompt(prompt, context)

            # 运行 Agent
            output = await self._engine.run(full_prompt)

            return ExecutionResult(
                success=True,
                output=output,
                metadata={
                    "session_id": self._engine.session_id,
                    "model": self._provider.model if self._provider else "unknown",
                },
            )

        except Exception as e:
            self._logger.error(f"Agent execution failed: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
            )

    async def execute_stream(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        流式执行 Agent

        Args:
            prompt: 用户输入
            context: 执行上下文 (可选)

        Yields:
            流式事件
        """
        if not self._initialized:
            raise RuntimeError("Executor not initialized. Call initialize() first.")

        self._logger.info(f"Starting streaming execution with prompt length: {len(prompt)}")

        try:
            # 合并上下文到提示词
            full_prompt = self._build_prompt(prompt, context)

            # 流式运行 Agent
            async for event in self._engine.run_stream(full_prompt):
                yield event

        except Exception as e:
            self._logger.error(f"Streaming execution failed: {e}")
            yield {"type": "error", "message": str(e)}

    def reset(self) -> None:
        """重置执行器状态"""
        if self._engine:
            self._engine.reset()
        self._logger.info("Executor reset")

    def get_context_summary(self) -> dict[str, Any]:
        """获取上下文摘要"""
        if self._engine:
            return self._engine.get_context_summary()
        return {}

    def _create_provider(self, agent_definition: dict[str, Any]) -> Any:
        """
        创建 Provider

        Args:
            agent_definition: Agent 定义

        Returns:
            Provider 实例
        """
        try:
            from pyagentforge.providers.factory import create_provider

            # 从定义中获取模型配置
            model_config = agent_definition.get("model", {})
            model_id = model_config.get("id", "claude-sonnet-4-20250514")

            # 创建 Provider
            provider = create_provider(
                model_id,
                temperature=model_config.get("temperature", 1.0),
                max_tokens=model_config.get("max_tokens", 4096),
            )

            self._logger.info(f"Created provider for model: {model_id}")
            return provider

        except ImportError:
            self._logger.warning("pyagentforge not available, using mock provider")
            return MockProvider()

    def _create_tool_registry(self, agent_definition: dict[str, Any]) -> Any:
        """
        创建工具注册表

        Args:
            agent_definition: Agent 定义

        Returns:
            ToolRegistry 实例
        """
        try:
            from pyagentforge.tools.registry import ToolRegistry
            from pyagentforge.kernel.executor import PermissionChecker

            # 创建工具注册表
            registry = ToolRegistry()

            # 注册内置工具
            registry.register_builtin_tools()

            # 从工作区域配置过滤工具
            capabilities = agent_definition.get("capabilities", {})
            allowed_tools = capabilities.get("tools", ["*"])
            denied_tools = capabilities.get("denied_tools", [])

            # 如果有拒绝列表或非通配符允许列表，过滤工具
            if denied_tools or "*" not in allowed_tools:
                registry = registry.filter_by_permission(allowed_tools)
                # 移除拒绝的工具
                for tool_name in denied_tools:
                    if tool_name in registry._tools:
                        registry.unregister(tool_name)

            # 创建权限检查器
            from .permission_bridge import (
                WorkspacePathValidator,
                WorkspacePermissionChecker,
                create_pyagentforge_permission_checker,
            )

            path_validator = WorkspacePathValidator(self._workspace_context)
            ws_checker = WorkspacePermissionChecker(
                workspace_config=self._workspace_context.config,
                path_validator=path_validator,
            )
            permission_checker = create_pyagentforge_permission_checker(ws_checker)

            # 存储权限检查器供后续使用
            self._permission_checker = permission_checker

            self._logger.info(f"Created tool registry with {len(registry)} tools")
            return registry

        except ImportError:
            self._logger.warning("pyagentforge not available, using mock registry")
            return MockToolRegistry()

    def _create_agent_config(
        self,
        agent_definition: dict[str, Any],
        system_prompt: str | None,
    ) -> Any:
        """
        创建 Agent 配置

        Args:
            agent_definition: Agent 定义
            system_prompt: 系统提示词

        Returns:
            AgentConfig 实例
        """
        try:
            from pyagentforge.kernel.engine import AgentConfig

            # 从定义中获取配置
            limits = agent_definition.get("limits", {})
            model_config = agent_definition.get("model", {})

            config = AgentConfig(
                system_prompt=system_prompt or agent_definition.get("identity", {}).get(
                    "description", "You are a helpful AI assistant."
                ),
                max_tokens=model_config.get("max_tokens", 4096),
                temperature=model_config.get("temperature", 1.0),
                max_iterations=limits.get("max_iterations", 100),
                permission_checker=getattr(self, "_permission_checker", None),
            )

            return config

        except ImportError:
            self._logger.warning("pyagentforge not available, using mock config")
            return MockAgentConfig(system_prompt or "You are a helpful AI assistant.")

    def _create_engine(self) -> Any:
        """
        创建 Agent 引擎

        Returns:
            AgentEngine 实例
        """
        try:
            from pyagentforge.kernel.engine import AgentEngine

            engine = AgentEngine(
                provider=self._provider,
                tool_registry=self._tool_registry,
                config=self._config,
            )

            self._logger.info(f"Created AgentEngine: session_id={engine.session_id}")
            return engine

        except ImportError:
            self._logger.warning("pyagentforge not available, using mock engine")
            return MockAgentEngine()

    def _build_prompt(self, prompt: str, context: dict[str, Any] | None) -> str:
        """
        构建完整提示词

        Args:
            prompt: 用户输入
            context: 执行上下文

        Returns:
            完整提示词
        """
        if not context:
            return prompt

        # 添加工作区域上下文
        workspace_info = f"""Working directory: {self._workspace_context.resolved_root}
Namespace: {self._workspace_context.config.namespace}
Read-only: {self._workspace_context.config.is_readonly}
"""
        context_str = "\n".join(f"- {k}: {v}" for k, v in context.items() if v is not None)

        if context_str:
            return f"{workspace_info}\nContext:\n{context_str}\n\nTask: {prompt}"
        return f"{workspace_info}\n\nTask: {prompt}"


# ==================== Mock 类 (用于测试或 pyagentforge 不可用时) ====================


class MockProvider:
    """Mock Provider"""

    def __init__(self) -> None:
        self.model = "mock-model"

    async def create_message(self, **kwargs: Any) -> Any:
        from dataclasses import dataclass

        @dataclass
        class MockResponse:
            text: str = "Mock response - pyagentforge not available"
            stop_reason: str = "end_turn"
            has_tool_calls: bool = False
            content: list = []
            tool_calls: list = []

        return MockResponse()


class MockToolRegistry:
    """Mock Tool Registry"""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def get_schemas(self) -> list[dict]:
        return []

    def get(self, name: str) -> Any:
        return None

    def register(self, tool: Any) -> None:
        pass

    def unregister(self, name: str) -> bool:
        return False

    def __len__(self) -> int:
        return 0


@dataclass
class MockAgentConfig:
    """Mock Agent Config"""

    system_prompt: str = "You are a helpful AI assistant."
    max_tokens: int = 4096
    temperature: float = 1.0
    max_iterations: int = 100
    permission_checker: Any = None


class MockAgentEngine:
    """Mock Agent Engine"""

    def __init__(self) -> None:
        self._session_id = "mock-session"

    @property
    def session_id(self) -> str:
        return self._session_id

    async def run(self, prompt: str) -> str:
        return "Mock response - pyagentforge not available"

    async def run_stream(self, prompt: str):
        yield {"type": "complete", "text": "Mock response - pyagentforge not available"}

    def reset(self) -> None:
        pass

    def get_context_summary(self) -> dict[str, Any]:
        return {"session_id": self._session_id}
