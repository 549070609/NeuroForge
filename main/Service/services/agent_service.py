"""
Agent Service - Agent 管理服务

提供 Agent 的加载、执行和计划管理功能。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.registry import ServiceRegistry
from ..services.base import BaseService
from ..schemas.agents import (
    AgentInfoResponse,
    AgentListResponse,
    AgentStatsResponse,
    NamespaceInfo,
    NamespaceListResponse,
    PlanCreate,
    PlanResponse,
    PlanListResponse,
    PlanStatsResponse,
    StepResponse,
    StepUpdateRequest,
    StepAddRequest,
)

# 延迟导入，避免循环依赖
# from Agent.core import AgentDirectory, AgentInfo, PlanFileManager, PlanFile, PlanStep
# from Agent.core.directory import AgentOrigin

logger = logging.getLogger(__name__)


class AgentService(BaseService):
    """
    Agent 管理服务

    继承 BaseService，提供:
    - Agent 目录扫描和管理
    - Agent 执行 (通过 pyagentforge)
    - 计划文件管理
    """

    def __init__(self, registry: ServiceRegistry):
        super().__init__(registry)
        self._directory = None  # AgentDirectory
        self._plan_manager = None  # PlanFileManager
        self._loader = None  # AgentLoader

    async def _on_initialize(self) -> None:
        """初始化服务"""
        # 延迟导入以避免循环依赖
        import sys

        # 确保 Agent 模块路径可用
        agent_path = Path("main/Agent")
        if str(agent_path) not in sys.path:
            sys.path.insert(0, str(agent_path.parent))

        try:
            from Agent.core import AgentDirectory, PlanFileManager

            # 初始化目录扫描器
            self._directory = AgentDirectory()
            self._directory.scan()

            # 初始化计划管理器
            self._plan_manager = PlanFileManager()

            self._logger.info("AgentService initialized")
        except ImportError as e:
            self._logger.warning(f"Agent module not fully available: {e}")
            self._directory = None
            self._plan_manager = None

    async def _on_shutdown(self) -> None:
        """关闭服务"""
        self._directory = None
        self._plan_manager = None
        self._logger.info("AgentService shut down")

    # ==================== Agent 管理 ====================

    def list_agents(
        self,
        namespace: str | None = None,
        tags: list[str] | None = None,
    ) -> AgentListResponse:
        """
        列出所有 Agent

        Args:
            namespace: 过滤命名空间
            tags: 过滤标签

        Returns:
            AgentListResponse
        """
        if not self._directory:
            return AgentListResponse(agents=[], total=0, namespaces=[])

        agents = self._directory.list_agents(namespace=namespace, tags=tags)

        agent_responses = []
        for agent in agents:
            metadata = agent.metadata
            limits = metadata.get("limits", {})
            capabilities = metadata.get("capabilities", {})

            agent_responses.append(
                AgentInfoResponse(
                    id=agent.agent_id,
                    name=agent.name,
                    namespace=agent.namespace,
                    origin=agent.origin.value,
                    description=agent.description,
                    tags=agent.tags,
                    category=agent.category,
                    is_readonly=limits.get("is_readonly", False),
                    max_concurrent=limits.get("max_concurrent", 3),
                    tools=capabilities.get("tools", ["*"]),
                    denied_tools=capabilities.get("denied_tools", []),
                )
            )

        return AgentListResponse(
            agents=agent_responses,
            total=len(agent_responses),
            namespaces=self._directory.list_namespaces(),
        )

    def get_agent(self, agent_id: str) -> AgentInfoResponse | None:
        """
        获取 Agent 详情

        Args:
            agent_id: Agent ID

        Returns:
            AgentInfoResponse 或 None
        """
        if not self._directory:
            return None

        agent = self._directory.get_agent(agent_id)
        if not agent:
            return None

        metadata = agent.metadata
        limits = metadata.get("limits", {})
        capabilities = metadata.get("capabilities", {})

        return AgentInfoResponse(
            id=agent.agent_id,
            name=agent.name,
            namespace=agent.namespace,
            origin=agent.origin.value,
            description=agent.description,
            tags=agent.tags,
            category=agent.category,
            is_readonly=limits.get("is_readonly", False),
            max_concurrent=limits.get("max_concurrent", 3),
            tools=capabilities.get("tools", ["*"]),
            denied_tools=capabilities.get("denied_tools", []),
        )

    def list_namespaces(self) -> NamespaceListResponse:
        """
        列出所有命名空间

        Returns:
            NamespaceListResponse
        """
        if not self._directory:
            return NamespaceListResponse(namespaces=[], total=0)

        namespaces = self._directory.list_namespaces()
        namespace_infos = []

        for ns in namespaces:
            agents = self._directory.list_agents(namespace=ns)
            namespace_infos.append(
                NamespaceInfo(
                    name=ns,
                    agent_count=len(agents),
                    agents=[a.agent_id for a in agents],
                )
            )

        return NamespaceListResponse(
            namespaces=namespace_infos,
            total=len(namespace_infos),
        )

    def get_stats(self) -> AgentStatsResponse:
        """
        获取 Agent 统计信息

        Returns:
            AgentStatsResponse
        """
        if not self._directory:
            return AgentStatsResponse(
                total_agents=0,
                total_namespaces=0,
                by_origin={},
                namespaces=[],
            )

        stats = self._directory.get_stats()
        return AgentStatsResponse(**stats)

    def refresh(self) -> None:
        """刷新 Agent 目录缓存"""
        if self._directory:
            self._directory.refresh()
            self._logger.info("Agent directory refreshed")

    # ==================== 计划管理 ====================

    def create_plan(self, request: PlanCreate) -> PlanResponse | None:
        """
        创建计划

        Args:
            request: PlanCreate 请求

        Returns:
            PlanResponse 或 None
        """
        if not self._plan_manager:
            return None

        steps_data = None
        if request.steps:
            steps_data = [step.model_dump() for step in request.steps]

        plan = self._plan_manager.create_plan(
            title=request.title,
            objective=request.objective,
            steps=steps_data,
            context=request.context or "",
            priority=request.priority,
            namespace=request.namespace,
            estimated_complexity=request.estimated_complexity,
            metadata=request.metadata,
        )

        return self._plan_to_response(plan)

    def get_plan(self, plan_id: str) -> PlanResponse | None:
        """
        获取计划

        Args:
            plan_id: 计划 ID

        Returns:
            PlanResponse 或 None
        """
        if not self._plan_manager:
            return None

        plan = self._plan_manager.get_plan(plan_id)
        if not plan:
            return None

        return self._plan_to_response(plan)

    def list_plans(
        self,
        namespace: str | None = None,
        status: str | None = None,
    ) -> PlanListResponse:
        """
        列出计划

        Args:
            namespace: 过滤命名空间
            status: 过滤状态

        Returns:
            PlanListResponse
        """
        if not self._plan_manager:
            return PlanListResponse(plans=[], total=0)

        from Agent.core.plan_manager import PlanStatus

        status_enum = None
        if status:
            try:
                status_enum = PlanStatus(status)
            except ValueError:
                pass

        plans = self._plan_manager.list_plans(namespace=namespace, status=status_enum)

        return PlanListResponse(
            plans=[self._plan_to_response(p) for p in plans],
            total=len(plans),
        )

    def update_step(
        self,
        plan_id: str,
        step_id: str,
        request: StepUpdateRequest,
    ) -> PlanResponse | None:
        """
        更新步骤状态

        Args:
            plan_id: 计划 ID
            step_id: 步骤 ID
            request: StepUpdateRequest 请求

        Returns:
            PlanResponse 或 None
        """
        if not self._plan_manager:
            return None

        from Agent.core.plan_manager import StepStatus

        status_enum = None
        if request.status:
            try:
                status_enum = StepStatus(request.status)
            except ValueError:
                pass

        plan = self._plan_manager.update_step(
            plan_id=plan_id,
            step_id=step_id,
            status=status_enum,
            notes=request.notes,
        )

        if not plan:
            return None

        return self._plan_to_response(plan)

    def add_step(
        self,
        plan_id: str,
        request: StepAddRequest,
    ) -> PlanResponse | None:
        """
        添加步骤到计划

        Args:
            plan_id: 计划 ID
            request: StepAddRequest 请求

        Returns:
            PlanResponse 或 None
        """
        if not self._plan_manager:
            return None

        plan = self._plan_manager.add_step(
            plan_id=plan_id,
            title=request.title,
            description=request.description or "",
            dependencies=request.dependencies,
            estimated_time=request.estimated_time or "",
            acceptance_criteria=request.acceptance_criteria,
            files_affected=request.files_affected,
        )

        if not plan:
            return None

        return self._plan_to_response(plan)

    def delete_plan(self, plan_id: str) -> bool:
        """
        删除计划

        Args:
            plan_id: 计划 ID

        Returns:
            是否成功
        """
        if not self._plan_manager:
            return False

        return self._plan_manager.delete_plan(plan_id)

    def get_plan_stats(self) -> PlanStatsResponse:
        """
        获取计划统计信息

        Returns:
            PlanStatsResponse
        """
        if not self._plan_manager:
            return PlanStatsResponse(total_plans=0, by_status={})

        stats = self._plan_manager.get_stats()
        return PlanStatsResponse(**stats)

    # ==================== Agent 执行 ====================

    async def execute_agent(
        self,
        agent_id: str,
        task: str,
        context: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute agent via real AgentExecutor runtime path."""
        started_at = datetime.utcnow()
        options = options or {}

        def _error_response(error: str) -> dict[str, Any]:
            completed_at = datetime.utcnow()
            return {
                "agent_id": agent_id,
                "status": "error",
                "result": None,
                "error": error,
                "plan_id": None,
                "started_at": started_at.isoformat() + "Z",
                "completed_at": completed_at.isoformat() + "Z",
            }

        agent_info = self.get_agent(agent_id)
        if not agent_info:
            return _error_response(f"Agent not found: {agent_id}")

        if not self._directory:
            return _error_response("Agent directory not available")

        agent = self._directory.get_agent(agent_id)
        if not agent:
            return _error_response(f"Agent not found: {agent_id}")

        system_prompt: str | None = None
        if agent.system_prompt_path and agent.system_prompt_path.exists():
            system_prompt = agent.system_prompt_path.read_text(encoding="utf-8")

        metadata = agent.metadata if isinstance(agent.metadata, dict) else {}
        capabilities = metadata.get("capabilities", {})
        limits = metadata.get("limits", {})

        root_path = options.get("workspace_root") or options.get("root_path") or str(Path.cwd())
        namespace = options.get("namespace") or getattr(agent, "namespace", "default")
        allowed_tools = options.get("allowed_tools") or options.get("tools") or capabilities.get("tools", ["*"])
        denied_tools = options.get("denied_tools") or capabilities.get("denied_tools", [])
        is_readonly = bool(options.get("is_readonly", limits.get("is_readonly", False)))

        from .proxy.agent_executor import AgentExecutor
        from .proxy.workspace_manager import WorkspaceConfig, WorkspaceContext

        workspace_config = WorkspaceConfig(
            root_path=root_path,
            namespace=namespace,
            allowed_tools=allowed_tools,
            denied_tools=denied_tools,
            is_readonly=is_readonly,
        )
        workspace_context = WorkspaceContext(
            workspace_id=f"agent-service-{agent_id}",
            config=workspace_config,
        )

        self._logger.info("Executing agent %s with real executor path", agent_id)

        try:
            executor = AgentExecutor(workspace_context)
            await executor.initialize(
                agent_definition=metadata,
                system_prompt=system_prompt,
                config_overrides=options,
            )
            result = await executor.execute(prompt=task, context=context)
            completed_at = datetime.utcnow()
            return {
                "agent_id": agent_id,
                "status": "completed" if result.success else "error",
                "result": result.output if result.success else None,
                "error": result.error if not result.success else None,
                "plan_id": None,
                "started_at": started_at.isoformat() + "Z",
                "completed_at": completed_at.isoformat() + "Z",
            }
        except Exception as exc:
            self._logger.exception("Agent execution failed for %s", agent_id)
            return _error_response(str(exc))

    # ==================== 辅助方法 ====================

    def _plan_to_response(self, plan: Any) -> PlanResponse:
        """转换 PlanFile 为 PlanResponse"""
        steps = []
        for step in plan.steps:
            steps.append(
                StepResponse(
                    id=step.id,
                    title=step.title,
                    status=step.status.value,
                    description=step.description,
                    dependencies=step.dependencies,
                    estimated_time=step.estimated_time,
                    acceptance_criteria=step.acceptance_criteria,
                    files_affected=step.files_affected,
                    notes=step.notes,
                    started_at=step.started_at,
                    completed_at=step.completed_at,
                )
            )

        return PlanResponse(
            id=plan.id,
            title=plan.title,
            objective=plan.objective,
            status=plan.status.value,
            priority=plan.priority,
            namespace=plan.namespace,
            estimated_complexity=plan.estimated_complexity,
            created=plan.created,
            updated=plan.updated,
            context=plan.context,
            steps=steps,
            progress=plan.get_progress(),
            change_log=plan.change_log,
        )
