"""
Agent Executor - Agent 鎵ц鍣?

闆嗘垚 pyagentforge 鏍稿績鍔熻兘锛屽湪宸ヤ綔鍖哄煙涓婁笅鏂囦腑鎵ц Agent銆?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from pyagentforge import (
    AgentEngine,
    AgentConfig,
    ToolRegistry,
    BaseProvider,
    register_core_tools,
    get_registry,
)
from pyagentforge.providers.factory import (
    create_provider_from_config,
    create_provider,
)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """鎵ц缁撴灉"""

    success: bool
    output: str
    error: str | None = None
    iterations: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentExecutor:
    """
    Agent 鎵ц鍣?

    鍦ㄥ伐浣滃尯鍩熶笂涓嬫枃涓墽琛?Agent锛岄泦鎴?pyagentforge 鏍稿績鍔熻兘銆?
    """

    def __init__(self, workspace_context: Any) -> None:
        """
        鍒濆鍖栨墽琛屽櫒

        Args:
            workspace_context: WorkspaceContext 瀹炰緥
        """
        self._workspace_context = workspace_context
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
        鍒濆鍖栨墽琛屽櫒

        Args:
            agent_definition: Agent 瀹氫箟 (鏉ヨ嚜 Agent 瀹氫箟鐨?metadata)
            system_prompt: 绯荤粺鎻愮ず璇?(鍙€?
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
        鎵ц Agent

        Args:
            prompt: 鐢ㄦ埛杈撳叆
            context: 鎵ц涓婁笅鏂?(鍙€?

        Returns:
            ExecutionResult
        """
        if not self._initialized:
            raise RuntimeError("Executor not initialized. Call initialize() first.")

        self._logger.info(f"Executing agent with prompt length: {len(prompt)}")

        try:
            # 鍚堝苟涓婁笅鏂囧埌鎻愮ず璇?
            full_prompt = self._build_prompt(prompt, context)

            # 杩愯 Agent
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
        娴佸紡鎵ц Agent

        Args:
            prompt: 鐢ㄦ埛杈撳叆
            context: 鎵ц涓婁笅鏂?(鍙€?

        Yields:
            娴佸紡浜嬩欢
        """
        if not self._initialized:
            raise RuntimeError("Executor not initialized. Call initialize() first.")

        self._logger.info(f"Starting streaming execution with prompt length: {len(prompt)}")

        try:
            # 鍚堝苟涓婁笅鏂囧埌鎻愮ず璇?
            full_prompt = self._build_prompt(prompt, context)

            # 娴佸紡杩愯 Agent
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

        _model_keys = {"provider", "model", "temperature", "max_tokens"}
        _limit_keys = {"max_iterations", "timeout"}

        for key, value in overrides.items():
            if value is None:
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

    def _create_provider(self, agent_definition: dict[str, Any]) -> Any:
        """Create a Provider instance from agent definition.

        Prefers the explicit-config path (``create_provider_from_config``) so
        that the Service layer controls which ``ModelConfig`` is used.  Falls
        back to the legacy ``create_provider(model_id)`` when the model is not
        found in the registry (e.g. ad-hoc / test scenarios).
        """
        try:
            model_section = agent_definition.get("model", {})
            model_id = model_section.get("id", "claude-sonnet-4-20250514")
            extra_kwargs: dict[str, Any] = {
                "temperature": model_section.get("temperature", 1.0),
                "max_tokens": model_section.get("max_tokens", 4096),
            }

            registry_config = get_registry().get_model(model_id)

            if registry_config:
                provider = create_provider_from_config(
                    registry_config, **extra_kwargs
                )
            else:
                import warnings
                warnings.warn(
                    f"Model '{model_id}' not found in registry; "
                    "falling back to legacy create_provider().",
                    DeprecationWarning,
                    stacklevel=2,
                )
                provider = create_provider(model_id, **extra_kwargs)

            self._logger.info(f"Created provider for model: {model_id}")
            return provider

        except ImportError as exc:
            self._raise_missing_dependency("provider", exc)

    def _create_tool_registry(self, agent_definition: dict[str, Any]) -> Any:
        """
        鍒涘缓宸ュ叿娉ㄥ唽琛?

        Args:
            agent_definition: Agent 瀹氫箟

        Returns:
            ToolRegistry 瀹炰緥
        """
        try:
            registry = ToolRegistry()
            register_core_tools(registry)

            # 浠庡伐浣滃尯鍩熼厤缃繃婊ゅ伐鍏?
            capabilities = agent_definition.get("capabilities", {})
            allowed_tools = capabilities.get("tools", ["*"])
            denied_tools = capabilities.get("denied_tools", [])

            # 濡傛灉鏈夋嫆缁濆垪琛ㄦ垨闈為€氶厤绗﹀厑璁稿垪琛紝杩囨护宸ュ叿
            if denied_tools or "*" not in allowed_tools:
                registry = registry.filter_by_permission(allowed_tools)
                # 绉婚櫎鎷掔粷鐨勫伐鍏?
                for tool_name in denied_tools:
                    registry.unregister(tool_name)

            # 鍒涘缓鏉冮檺妫€鏌ュ櫒
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

            # 瀛樺偍鏉冮檺妫€鏌ュ櫒渚涘悗缁娇鐢?
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
        鍒涘缓 Agent 閰嶇疆

        Args:
            agent_definition: Agent 瀹氫箟
            system_prompt: 绯荤粺鎻愮ず璇?

        Returns:
            AgentConfig 瀹炰緥
        """
        try:
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

        except ImportError as exc:
            self._raise_missing_dependency("agent config", exc)

    def _create_engine(self) -> Any:
        """
        鍒涘缓 Agent 寮曟搸

        Returns:
            AgentEngine 瀹炰緥
        """
        try:
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
        鏋勫缓瀹屾暣鎻愮ず璇?

        Args:
            prompt: 鐢ㄦ埛杈撳叆
            context: 鎵ц涓婁笅鏂?

        Returns:
            瀹屾暣鎻愮ず璇?
        """
        if not context:
            return prompt

        # 娣诲姞宸ヤ綔鍖哄煙涓婁笅鏂?
        workspace_info = f"""Working directory: {self._workspace_context.resolved_root}
Namespace: {self._workspace_context.config.namespace}
Read-only: {self._workspace_context.config.is_readonly}
"""
        context_str = "\n".join(f"- {k}: {v}" for k, v in context.items() if v is not None)

        if context_str:
            return f"{workspace_info}\nContext:\n{context_str}\n\nTask: {prompt}"
        return f"{workspace_info}\n\nTask: {prompt}"






