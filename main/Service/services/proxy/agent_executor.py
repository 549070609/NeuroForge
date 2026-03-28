"""
Agent Executor - Agent 执行器

集成 pyagentforge 核心功能，在工作区上下文中执行 Agent。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from pyagentforge import (
    AgentEngine,
    AgentConfig,
    ToolRegistry,
    register_core_tools,
)
from pyagentforge.client import LLMClient
from pyagentforge.kernel.base_provider import BaseProvider

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


class LLMClientProvider(BaseProvider):
    """Bridge LLMClient into AgentEngine's BaseProvider contract."""

    def __init__(
        self,
        llm_client: LLMClient,
        model_id: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ) -> None:
        super().__init__(model=model_id, max_tokens=max_tokens, temperature=temperature)
        self._llm_client = llm_client

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ):
        max_tokens = kwargs.pop("max_tokens", self.max_tokens)
        temperature = kwargs.pop("temperature", self.temperature)
        return await self._llm_client.create_message(
            model_id=self.model,
            messages=messages,
            system=system,
            tools=tools or [],
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        return await self._llm_client.count_tokens(
            model_id=self.model,
            messages=messages,
        )

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ):
        max_tokens = kwargs.pop("max_tokens", self.max_tokens)
        temperature = kwargs.pop("temperature", self.temperature)
        async for chunk in self._llm_client.stream_message(
            model_id=self.model,
            messages=messages,
            system=system,
            tools=tools or [],
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        ):
            yield chunk


class AgentExecutor:
    """
    Agent 执行器

    在工作区上下文中执行 Agent，集成 pyagentforge 核心功能。
    """

    def __init__(self, workspace_context: Any) -> None:
        """
        初始化执行器

        Args:
            workspace_context: WorkspaceContext 实例
        """
        self._workspace_context = workspace_context
        self._model_id: str = "default"
        self._llm_client: LLMClient | None = None
        self._provider: BaseProvider | None = None
        self._tool_registry: ToolRegistry | None = None
        self._engine: AgentEngine | None = None
        self._config: AgentConfig | None = None
        self._initialized = False
        self._logger = logging.getLogger(f"{__name__}.AgentExecutor")

    async def initialize(
        self,
        agent_definition: dict[str, Any],
        system_prompt: str | None = None,
        config_overrides: dict[str, Any] | None = None,
    ) -> None:
        """
        初始化执行器

        Args:
            agent_definition: Agent 定义 (来自 Agent 定义的 metadata)
            system_prompt: 系统提示词(可选)
        """
        if self._initialized:
            self._logger.warning("Executor already initialized")
            return

        try:
            # 应用运行时配置覆盖（优先级高于 agent.yaml）
            if config_overrides:
                agent_definition = self._apply_config_overrides(agent_definition, config_overrides)
                if config_overrides.get("system_prompt"):
                    system_prompt = config_overrides["system_prompt"]
                self._logger.info("Applied config overrides: %s", list(config_overrides.keys()))

            # 获取模型 ID
            model_section = agent_definition.get("model", {})
            self._model_id = (
                model_section.get("id")
                or model_section.get("model")
                or self._model_id
            )

            # 创建 LLM 客户端
            self._llm_client = self._create_llm_client()

            # 创建工具注册表
            self._tool_registry = self._create_tool_registry(agent_definition)

            # 创建 Agent 配置
            self._config = self._create_agent_config(agent_definition, system_prompt)

            # 创建 Provider
            self._provider = self._create_provider()

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
            context: 执行上下文(可选)

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
                    "model": self._model_id,
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
            context: 执行上下文(可选)

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
        """Reset executor state."""
        if self._engine:
            self._engine.reset()
        self._logger.info("Executor reset")

    def get_context_summary(self) -> dict[str, Any]:
        """Get execution context summary."""
        if self._engine:
            return self._engine.get_context_summary()
        return {}

    def _apply_config_overrides(
        self,
        definition: dict[str, Any],
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        """
        将运行时配置覆盖合并到 agent 定义字典。

        支持的覆盖字段:
          model 层: provider, model, temperature, max_tokens
          limits 层: max_iterations, timeout
          其他: system_prompt (由 initialize 直接处理), extra (透传)

        Args:
            definition: 原始 agent 定义（来自 agent.yaml）
            overrides: 运行时覆盖字典

        Returns:
            深拷贝后已合并覆盖的 agent 定义
        """
        import copy

        definition = copy.deepcopy(definition)

        _model_keys = {"provider", "model", "id", "temperature", "max_tokens"}
        _limit_keys = {"max_iterations", "timeout"}

        for key, value in overrides.items():
            if value is None:
                continue
            if key == "model_id":
                definition.setdefault("model", {})["id"] = value
                continue
            if key in _model_keys:
                definition.setdefault("model", {})[key] = value
            elif key in _limit_keys:
                definition.setdefault("limits", {})[key] = value
            elif key == "extra" and isinstance(value, dict):
                definition.setdefault("extra", {}).update(value)
            # "system_prompt" is handled in initialize()

        return definition

    def _raise_missing_dependency(self, component: str, exc: ImportError) -> None:
        """Fail fast when pyagentforge cannot be imported."""
        message = (
            f"pyagentforge is required to initialize {component}. "
            "Install it or ensure 'main/agentforge-engine' is on PYTHONPATH."
        )
        self._logger.error(message)
        raise RuntimeError(message) from exc

    def _create_llm_client(self) -> LLMClient:
        """创建 LLM 客户端"""
        try:
            client = LLMClient()
            self._logger.info(f"Created LLM client for model: {self._model_id}")
            return client
        except ImportError as exc:
            self._raise_missing_dependency("llm client", exc)

    def _create_tool_registry(self, agent_definition: dict[str, Any]) -> Any:
        """
        创建工具注册表

        Args:
            agent_definition: Agent 定义

        Returns:
            ToolRegistry 实例
        """
        try:
            registry = ToolRegistry()
            register_core_tools(registry)

            # 从工作区配置过滤工具
            capabilities = agent_definition.get("capabilities", {})
            allowed_tools = capabilities.get("tools", ["*"])
            denied_tools = capabilities.get("denied_tools", [])

            # 如果有拒绝列表或非通配符允许列表，过滤工具
            if denied_tools or "*" not in allowed_tools:
                registry = registry.filter_by_permission(allowed_tools)
                # 移除拒绝的工具
                for tool_name in denied_tools:
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

        except ImportError as exc:
            self._raise_missing_dependency("tool registry", exc)

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
            limits = agent_definition.get("limits", {})
            model_config = agent_definition.get("model", {})

            config = AgentConfig(
                name=agent_definition.get("identity", {}).get("name", "default"),
                description=agent_definition.get("identity", {}).get("description", ""),
                version=agent_definition.get("identity", {}).get("version", "1.0.0"),
                model=model_config.get("id") or model_config.get("model") or self._model_id,
                system_prompt=system_prompt or agent_definition.get("identity", {}).get(
                    "description", "You are a helpful AI assistant."
                ),
                max_tokens=model_config.get("max_tokens", 4096),
                temperature=model_config.get("temperature", 1.0),
                timeout=model_config.get("timeout", limits.get("timeout", 120)),
                allowed_tools=agent_definition.get("capabilities", {}).get("tools", ["*"]),
                denied_tools=agent_definition.get("capabilities", {}).get("denied_tools", []),
                ask_tools=agent_definition.get("capabilities", {}).get("ask_tools", []),
                max_iterations=limits.get("max_iterations", 100),
                max_subagent_depth=limits.get("max_subagent_depth", 3),
                permission_checker=getattr(self, "_permission_checker", None),
            )

            return config

        except ImportError as exc:
            self._raise_missing_dependency("agent config", exc)

    def _create_provider(self) -> BaseProvider:
        if self._llm_client is None:
            raise RuntimeError("LLM client is not initialized")
        if self._config is None:
            raise RuntimeError("Agent config is not initialized")
        return LLMClientProvider(
            llm_client=self._llm_client,
            model_id=self._model_id,
            max_tokens=self._config.max_tokens,
            temperature=self._config.temperature,
        )

    def _create_engine(self) -> Any:
        """
        创建 Agent 引擎

        Returns:
            AgentEngine 实例
        """
        try:
            if self._provider is None:
                raise RuntimeError("Provider is not initialized")
            if self._tool_registry is None:
                raise RuntimeError("Tool registry is not initialized")
            if self._config is None:
                raise RuntimeError("Agent config is not initialized")
            engine = AgentEngine(
                provider=self._provider,
                tool_registry=self._tool_registry,
                config=self._config,
            )

            self._logger.info(f"Created AgentEngine: session_id={engine.session_id}")
            return engine

        except ImportError as exc:
            self._raise_missing_dependency("agent engine", exc)

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

        # 添加工作区上下文
        root = getattr(self._workspace_context, "resolved_root", None)
        if root is None:
            root = getattr(self._workspace_context, "root_path", "")
        workspace_info = f"""Working directory: {root}
Namespace: {self._workspace_context.config.namespace}
Read-only: {self._workspace_context.config.is_readonly}
"""
        context_str = "\n".join(f"- {k}: {v}" for k, v in context.items() if v is not None)

        if context_str:
            return f"{workspace_info}\nContext:\n{context_str}\n\nTask: {prompt}"
        return f"{workspace_info}\n\nTask: {prompt}"
