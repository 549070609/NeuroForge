"""
Agent Proxy Service - 代理 Agent 服务

提供工作区域管理、会话管理和 Agent 执行的主服务。
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from ...core.registry import ServiceRegistry
from ...services.base import BaseService
from .workspace_manager import WorkspaceConfig, WorkspaceContext, WorkspaceManager
from .permission_bridge import WorkspacePathValidator, create_permission_checker_from_workspace
from .agent_executor import AgentExecutor, ExecutionResult
from .session_manager import SessionManager, SessionState

logger = logging.getLogger(__name__)


class AgentProxyService(BaseService):
    """
    代理 Agent 服务

    继承 BaseService，提供:
    - 工作区域管理 (创建、查询、删除)
    - 会话管理 (创建、查询、删除)
    - Agent 执行 (同步和流式)
    """

    def __init__(self, registry: ServiceRegistry) -> None:
        super().__init__(registry)
        self._workspace_manager: WorkspaceManager | None = None
        self._session_manager: SessionManager | None = None
        self._agent_directory: Any = None  # AgentDirectory
        self._executor_cache: dict[str, AgentExecutor] = {}

    async def _on_initialize(self) -> None:
        """初始化服务"""
        self._logger.info("Initializing AgentProxyService...")

        # 初始化管理器
        self._workspace_manager = WorkspaceManager()
        self._session_manager = SessionManager()

        # 延迟导入 Agent 模块
        try:
            import sys
            from pathlib import Path

            agent_path = Path("main/Agent")
            if str(agent_path) not in sys.path:
                sys.path.insert(0, str(agent_path.parent))

            from Agent.core import AgentDirectory

            self._agent_directory = AgentDirectory()
            self._agent_directory.scan()
            self._logger.info("Agent directory loaded")

        except ImportError as e:
            self._logger.warning(f"Agent module not fully available: {e}")
            self._agent_directory = None

        self._logger.info("AgentProxyService initialized")

    async def _on_shutdown(self) -> None:
        """关闭服务"""
        self._logger.info("Shutting down AgentProxyService...")

        # 清理执行器缓存
        for executor in self._executor_cache.values():
            try:
                executor.reset()
            except Exception as e:
                self._logger.warning(f"Failed to reset executor: {e}")

        self._executor_cache.clear()

        # 清理会话
        if self._session_manager:
            self._session_manager.clear()

        # 清理工作区域
        if self._workspace_manager:
            self._workspace_manager.clear()

        self._logger.info("AgentProxyService shut down")

    # ==================== 工作区域管理 ====================

    def create_workspace(
        self,
        workspace_id: str,
        root_path: str,
        namespace: str = "default",
        allowed_tools: list[str] | None = None,
        denied_tools: list[str] | None = None,
        is_readonly: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        创建工作区域

        Args:
            workspace_id: 工作区域 ID
            root_path: 根路径
            namespace: 命名空间
            allowed_tools: 允许的工具列表
            denied_tools: 拒绝的工具列表
            is_readonly: 是否只读
            **kwargs: 其他配置参数

        Returns:
            工作区域信息
        """
        if not self._workspace_manager:
            raise RuntimeError("Service not initialized")

        config = WorkspaceConfig(
            root_path=root_path,
            namespace=namespace,
            allowed_tools=allowed_tools or ["*"],
            denied_tools=denied_tools or [],
            is_readonly=is_readonly,
            **kwargs,
        )

        context = self._workspace_manager.create_workspace(workspace_id, config)

        return {
            "workspace_id": workspace_id,
            "root_path": str(context.resolved_root),
            "namespace": context.config.namespace,
            "is_readonly": context.config.is_readonly,
            "allowed_tools": context.config.allowed_tools,
            "denied_tools": context.config.denied_tools,
        }

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        """
        获取工作区域信息

        Args:
            workspace_id: 工作区域 ID

        Returns:
            工作区域信息或 None
        """
        if not self._workspace_manager:
            return None

        context = self._workspace_manager.get_workspace(workspace_id)
        if not context:
            return None

        return {
            "workspace_id": workspace_id,
            "root_path": str(context.resolved_root),
            "namespace": context.config.namespace,
            "is_readonly": context.config.is_readonly,
            "allowed_tools": context.config.allowed_tools,
            "denied_tools": context.config.denied_tools,
        }

    async def remove_workspace(self, workspace_id: str) -> bool:
        """
        移除工作区域

        注意：这不会删除文件系统上的目录。

        Args:
            workspace_id: 工作区域 ID

        Returns:
            是否成功移除
        """
        if not self._workspace_manager:
            return False

        # 先清理关联的会话
        if self._session_manager:
            sessions = self._session_manager.list_sessions(workspace_id=workspace_id)
            for session in sessions:
                self._executor_cache.pop(session.session_id, None)
                await self._session_manager.delete_session(session.session_id)

        return self._workspace_manager.remove_workspace(workspace_id)

    def list_workspaces(self) -> list[str]:
        """列出所有工作区域"""
        if not self._workspace_manager:
            return []
        return self._workspace_manager.list_workspaces()

    # ==================== 会话管理 ====================

    async def create_session(
        self,
        workspace_id: str,
        agent_id: str,
        metadata: dict[str, Any] | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> SessionState:
        """
        创建会话

        Args:
            workspace_id: 工作区域 ID
            agent_id: Agent ID
            metadata: 元数据
            agent_config: 运行时配置覆盖（优先级高于 agent.yaml）

        Returns:
            SessionState

        Raises:
            ValueError: 如果工作区域不存在
        """
        if not self._workspace_manager or not self._session_manager:
            raise RuntimeError("Service not initialized")

        # 验证工作区域存在
        workspace = self._workspace_manager.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")

        # 创建执行器（携带运行时配置覆盖）
        executor = await self._create_executor(workspace, agent_id, config_overrides=agent_config)

        # 将 agent_config 持久化到 metadata，供执行器缓存失效时重建使用
        merged_metadata = dict(metadata or {})
        if agent_config:
            merged_metadata["_agent_config"] = agent_config

        # 创建会话
        session = await self._session_manager.create_session(
            workspace_id=workspace_id,
            agent_id=agent_id,
            metadata=merged_metadata,
            executor=executor,
        )

        # 缓存执行器
        self._executor_cache[session.session_id] = executor

        return session

    async def get_session(self, session_id: str) -> SessionState | None:
        """获取会话"""
        if not self._session_manager:
            return None
        return await self._session_manager.get_session(session_id)

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if not self._session_manager:
            return False

        # 清理执行器缓存
        if session_id in self._executor_cache:
            del self._executor_cache[session_id]

        return await self._session_manager.delete_session(session_id)

    async def list_sessions(
        self,
        workspace_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[SessionState]:
        """列出租话"""
        if not self._session_manager:
            return []
        return self._session_manager.list_sessions(workspace_id=workspace_id, agent_id=agent_id)

    # ==================== Agent 执行 ====================

    async def execute(
        self,
        session_id: str,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        执行 Agent

        Args:
            session_id: 会话 ID
            prompt: 用户输入
            context: 执行上下文

        Returns:
            ExecutionResult

        Raises:
            ValueError: 如果会话不存在
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        executor = self._executor_cache.get(session_id)
        if not executor or not executor._initialized:
            # 重新创建执行器（从 session metadata 恢复配置覆盖）
            workspace = self._workspace_manager.get_workspace(session.workspace_id)
            if not workspace:
                raise ValueError(f"Workspace not found: {session.workspace_id}")

            saved_config = session.metadata.get("_agent_config") if session.metadata else None
            executor = await self._create_executor(
                workspace, session.agent_id, config_overrides=saved_config
            )
            self._executor_cache[session_id] = executor

        # 添加用户消息到历史
        await self._session_manager.add_message(session_id, "user", prompt)

        # 执行
        result = await executor.execute(prompt, context)

        # 添加助手响应到历史
        if result.success:
            await self._session_manager.add_message(session_id, "assistant", result.output)
        else:
            await self._session_manager.add_message(
                session_id, "assistant", f"Error: {result.error}"
            )

        return result

    async def execute_stream(
        self,
        session_id: str,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        流式执行 Agent

        Args:
            session_id: 会话 ID
            prompt: 用户输入
            context: 执行上下文

        Yields:
            流式事件
        """
        session = await self.get_session(session_id)
        if not session:
            yield {"type": "error", "message": f"Session not found: {session_id}"}
            return

        executor = self._executor_cache.get(session_id)
        if not executor or not executor._initialized:
            workspace = self._workspace_manager.get_workspace(session.workspace_id)
            if not workspace:
                yield {"type": "error", "message": f"Workspace not found: {session.workspace_id}"}
                return

            saved_config = session.metadata.get("_agent_config") if session.metadata else None
            executor = await self._create_executor(
                workspace, session.agent_id, config_overrides=saved_config
            )
            self._executor_cache[session_id] = executor

        # 添加用户消息到历史
        await self._session_manager.add_message(session_id, "user", prompt)

        # 流式执行
        final_text = ""
        async for event in executor.execute_stream(prompt, context):
            yield event

            if event.get("type") == "complete":
                final_text = event.get("text", "")
            elif event.get("type") == "error":
                final_text = f"Error: {event.get('message', 'Unknown error')}"

        # 添加助手响应到历史
        if final_text:
            await self._session_manager.add_message(session_id, "assistant", final_text)

    # ==================== 辅助方法 ====================

    async def _create_executor(
        self,
        workspace: WorkspaceContext,
        agent_id: str,
        config_overrides: dict[str, Any] | None = None,
    ) -> AgentExecutor:
        """
        创建 Agent 执行器

        Args:
            workspace: 工作区域上下文
            agent_id: Agent ID
            config_overrides: 运行时配置覆盖，优先级高于 agent.yaml

        Returns:
            AgentExecutor 实例
        """
        # 获取 Agent 定义
        agent_definition = await self._get_agent_definition(agent_id)

        # 读取系统提示词
        system_prompt = await self._get_system_prompt(agent_id)

        # 创建执行器（传入运行时覆盖）
        executor = AgentExecutor(workspace)
        await executor.initialize(agent_definition, system_prompt, config_overrides=config_overrides)

        return executor

    async def _get_agent_definition(self, agent_id: str) -> dict[str, Any]:
        """获取 Agent 定义"""
        if self._agent_directory:
            agent_info = self._agent_directory.get_agent(agent_id)
            if agent_info:
                return agent_info.metadata

        # 返回默认定义
        return {
            "identity": {"name": agent_id, "description": f"Agent: {agent_id}"},
            "model": {"id": "claude-sonnet-4-20250514"},
            "capabilities": {"tools": ["*"]},
            "limits": {},
        }

    async def _get_system_prompt(self, agent_id: str) -> str | None:
        """获取系统提示词"""
        if self._agent_directory:
            agent_info = self._agent_directory.get_agent(agent_id)
            if agent_info and agent_info.system_prompt_path:
                try:
                    return agent_info.system_prompt_path.read_text(encoding="utf-8")
                except Exception as e:
                    self._logger.warning(f"Failed to read system prompt: {e}")

        return None

    def get_stats(self) -> dict[str, Any]:
        """获取服务统计信息"""
        return {
            "workspaces": self._workspace_manager.get_stats() if self._workspace_manager else {},
            "sessions": self._session_manager.get_stats() if self._session_manager else {},
            "executor_cache_size": len(self._executor_cache),
        }
