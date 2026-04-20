"""Agent proxy service for workspace/session execution and workflow orchestration."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


def _utcnow() -> datetime:
    """Return a naive UTC datetime (timezone stripped for backward compat)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from pyagentforge import FileCheckpointer
from pyagentforge.workflow import (
    AgentRole,
    SpanKind,
    SpanStatus,
    StepNode,
    TeamDefinition,
    TeamExecutor,
    TeamProcess,
    TraceCollector,
    WorkflowGraph,
)

from ...config import get_settings
from ...core.registry import ServiceRegistry
from ...persistence import StateStore, StoreRecord, create_store
from ...services.base import BaseService
from .agent_executor import AgentExecutor, ExecutionResult
from .governance import (
    GuardrailEngine,
    GuardrailResult,
    HandoffProtocol,
    HumanApprovalManager,
    SLOManager,
)
from .session_manager import SessionManager, SessionState
from .workspace_manager import WorkspaceConfig, WorkspaceContext, WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ExecutionGateFailure:
    error_message: str
    requires_approval: bool
    metadata: dict[str, Any]


class AgentProxyService(BaseService):
    """Proxy Agent service with persistence, workflow API, and tracing."""

    WORKFLOW_NAMESPACE = "workflow"
    TRACE_NAMESPACE = "trace"
    TASK_NAMESPACE = "task"
    PLAN_NAMESPACE = "plan"

    def __init__(self, registry: ServiceRegistry) -> None:
        super().__init__(registry)
        self._workspace_manager: WorkspaceManager | None = None
        self._session_manager: SessionManager | None = None
        self._agent_directory: Any = None
        self._executor_cache: dict[str, AgentExecutor] = {}
        self._store: StateStore | None = None
        self._workflow_checkpointer: FileCheckpointer | None = None
        self._session_ttl: int = 3600
        self._guardrails_enabled = True
        self._hitl_enabled = True
        self._guardrail_engine: GuardrailEngine | None = None
        self._approval_manager: HumanApprovalManager | None = None
        self._handoff_protocol: HandoffProtocol | None = None
        self._slo_manager: SLOManager | None = None

    async def _on_initialize(self) -> None:
        self._logger.info("Initializing AgentProxyService...")

        settings = get_settings()
        self._session_ttl = settings.session_ttl
        self._store = create_store(settings)
        self._guardrails_enabled = settings.guardrails_enabled
        self._hitl_enabled = settings.hitl_enabled

        self._workspace_manager = WorkspaceManager()
        self._session_manager = SessionManager(
            store=self._store,
            session_ttl=settings.session_ttl,
            max_sessions=settings.max_sessions,
        )
        self._guardrail_engine = GuardrailEngine()
        self._approval_manager = HumanApprovalManager(
            store=self._store,
            approval_ttl=settings.approval_ttl,
            auto_approve=settings.approval_auto_approve,
        )
        self._handoff_protocol = HandoffProtocol()
        self._slo_manager = SLOManager(
            store=self._store,
            window_size=settings.slo_window_size,
            target_success_rate=settings.slo_target_success_rate,
            target_p95_ms=settings.slo_target_p95_ms,
            circuit_failure_threshold=settings.circuit_failure_threshold,
            circuit_open_seconds=settings.circuit_open_seconds,
        )

        checkpoints_dir = Path(settings.sqlite_path).parent / "workflow_checkpoints"
        self._workflow_checkpointer = FileCheckpointer(checkpoints_dir)

        try:
            import sys

            agent_path = Path("main/Agent")
            if str(agent_path) not in sys.path:
                sys.path.insert(0, str(agent_path.parent))

            from Agent.core import AgentDirectory

            self._agent_directory = AgentDirectory()
            self._agent_directory.scan()
            self._logger.info("Agent directory loaded")
        except ImportError as exc:
            self._logger.warning("Agent module not fully available: %s", exc)
            self._agent_directory = None

        self._logger.info("AgentProxyService initialized")

    async def _on_shutdown(self) -> None:
        self._logger.info("Shutting down AgentProxyService...")

        for executor in self._executor_cache.values():
            try:
                executor.reset()
            except Exception as exc:
                self._logger.warning("Failed to reset executor: %s", exc)
        self._executor_cache.clear()

        if self._session_manager:
            await self._session_manager.clear()

        if self._workspace_manager:
            self._workspace_manager.clear()

        if self._store:
            await self._store.close()

        self._logger.info("AgentProxyService shut down")

    # ==================== Workspace ====================

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
        if not self._workspace_manager:
            return False

        if self._session_manager:
            sessions = await self._session_manager.list_sessions(workspace_id=workspace_id)
            for session in sessions:
                self._executor_cache.pop(session.session_id, None)
                self._session_manager.remove_executor(session.session_id)
                await self._session_manager.delete_session(session.session_id)

        return self._workspace_manager.remove_workspace(workspace_id)

    def list_workspaces(self) -> list[str]:
        if not self._workspace_manager:
            return []
        return self._workspace_manager.list_workspaces()

    # ==================== Session ====================

    async def create_session(
        self,
        workspace_id: str,
        agent_id: str,
        metadata: dict[str, Any] | None = None,
        agent_config: dict[str, Any] | None = None,
    ) -> SessionState:
        if not self._workspace_manager or not self._session_manager:
            raise RuntimeError("Service not initialized")

        workspace = self._workspace_manager.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")

        executor = await self._create_executor(workspace, agent_id, config_overrides=agent_config)

        merged_metadata = dict(metadata or {})
        if agent_config:
            merged_metadata["_agent_config"] = agent_config

        session = await self._session_manager.create_session(
            workspace_id=workspace_id,
            agent_id=agent_id,
            metadata=merged_metadata,
            executor=executor,
            idempotency_key=merged_metadata.get("idempotency_key"),
        )

        self._executor_cache[session.session_id] = executor
        self._session_manager.set_executor(session.session_id, executor)

        await self._bootstrap_session_state(session)
        return session

    async def get_session(self, session_id: str) -> SessionState | None:
        if not self._session_manager:
            return None
        return await self._session_manager.get_session(session_id)

    async def delete_session(self, session_id: str) -> bool:
        if not self._session_manager:
            return False

        self._executor_cache.pop(session_id, None)
        self._session_manager.remove_executor(session_id)

        deleted = await self._session_manager.delete_session(session_id)
        if deleted and self._store:
            await self._delete_session_scoped_state(session_id)
        return deleted

    async def list_sessions(
        self,
        workspace_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[SessionState]:
        if not self._session_manager:
            return []
        return await self._session_manager.list_sessions(workspace_id=workspace_id, agent_id=agent_id)

    # ==================== Execution ====================

    async def execute(
        self,
        session_id: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> ExecutionResult:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        executor = await self._ensure_executor_for_session(session)
        runtime_context = dict(context or {})
        start = perf_counter()
        failure_class: str | None = None
        scope = f"execute:{session.agent_id}"

        collector = self._new_trace_collector(trace_id)
        root_span = collector.start_span(
            "proxy.execute",
            kind=SpanKind.AGENT,
            attributes={
                "session_id": session_id,
                "workspace_id": session.workspace_id,
                "agent_id": session.agent_id,
            },
        )

        executor.set_trace_collector(collector)
        await self._session_manager.add_message(session_id, "user", prompt)

        try:
            allowed, reason = self._should_allow(scope)
            if not allowed:
                failure_class = "circuit_open"
                result = ExecutionResult(success=False, output="", error=reason, metadata={})
                await self._session_manager.add_message(session_id, "assistant", f"Error: {reason}")
            else:
                gate = await self._guard_execution_input(
                    session=session,
                    scope_kind="execute",
                    prompt=prompt,
                    context=runtime_context,
                )
                if gate is not None:
                    failure_class = "guardrail_review" if gate.requires_approval else "guardrail_blocked"
                    result = ExecutionResult(
                        success=False,
                        output="",
                        error=gate.error_message,
                        metadata=gate.metadata,
                    )
                    await self._session_manager.add_message(
                        session_id,
                        "assistant",
                        f"Error: {gate.error_message}",
                    )
                else:
                    result = await executor.execute(prompt, runtime_context)
                    output_guardrail = self._evaluate_output_guardrail(result.output if result.success else "")
                    if output_guardrail and output_guardrail.blocked:
                        failure_class = "output_guardrail_blocked"
                        top = output_guardrail.top_decision()
                        blocked_message = (
                            top.message
                            if top is not None
                            else "Output blocked by governance policy."
                        )
                        result = ExecutionResult(
                            success=False,
                            output="",
                            error=blocked_message,
                            iterations=result.iterations,
                            tool_calls=result.tool_calls,
                            metadata={
                                **result.metadata,
                                "guardrail": output_guardrail.to_dict(),
                                "failure_class": failure_class,
                            },
                        )
                        await self._session_manager.add_message(
                            session_id,
                            "assistant",
                            f"Error: {blocked_message}",
                        )
                    elif result.success:
                        await self._session_manager.add_message(session_id, "assistant", result.output)
                    else:
                        failure_class = failure_class or "execution_error"
                        await self._session_manager.add_message(
                            session_id,
                            "assistant",
                            f"Error: {result.error}",
                        )

            collector.finish_span(root_span, status=SpanStatus.OK if result.success else SpanStatus.ERROR)
        except Exception:
            collector.finish_span(root_span, status=SpanStatus.ERROR)
            latency_ms = int((perf_counter() - start) * 1000)
            await self._record_slo(
                scope=scope,
                success=False,
                latency_ms=latency_ms,
                failure_class=failure_class or "runtime_exception",
            )
            raise

        await self._persist_trace(
            collector,
            session_id=session_id,
            workflow_id=None,
            scope="execute",
        )
        await self._session_manager.update_session(session_id, {"trace_id": collector.trace_id})

        latency_ms = int((perf_counter() - start) * 1000)
        await self._record_slo(
            scope=scope,
            success=result.success,
            latency_ms=latency_ms,
            failure_class=failure_class if not result.success else None,
        )

        result.metadata.update(
            {
                "trace_id": collector.trace_id,
                "span_id": root_span.span_id,
                "latency_ms": latency_ms,
            }
        )
        return result

    async def execute_stream(
        self,
        session_id: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        session = await self.get_session(session_id)
        if not session:
            yield {"type": "error", "message": f"Session not found: {session_id}"}
            return

        executor = await self._ensure_executor_for_session(session)
        runtime_context = dict(context or {})
        start = perf_counter()
        failure_class: str | None = None
        scope = f"execute_stream:{session.agent_id}"

        collector = self._new_trace_collector(trace_id)
        root_span = collector.start_span(
            "proxy.execute_stream",
            kind=SpanKind.AGENT,
            attributes={
                "session_id": session_id,
                "workspace_id": session.workspace_id,
                "agent_id": session.agent_id,
            },
        )
        executor.set_trace_collector(collector)

        await self._session_manager.add_message(session_id, "user", prompt)

        try:
            allowed, reason = self._should_allow(scope)
            if not allowed:
                failure_class = "circuit_open"
                error_event = {
                    "type": "error",
                    "message": reason,
                    "trace_id": collector.trace_id,
                    "span_id": root_span.span_id,
                }
                yield error_event
                await self._session_manager.add_message(session_id, "assistant", f"Error: {reason}")
                collector.finish_span(root_span, status=SpanStatus.ERROR)
            else:
                gate = await self._guard_execution_input(
                    session=session,
                    scope_kind="execute_stream",
                    prompt=prompt,
                    context=runtime_context,
                )
                if gate is not None:
                    failure_class = "guardrail_review" if gate.requires_approval else "guardrail_blocked"
                    error_event = {
                        "type": "error",
                        "message": gate.error_message,
                        "trace_id": collector.trace_id,
                        "span_id": root_span.span_id,
                    }
                    error_event.update(gate.metadata)
                    yield error_event
                    await self._session_manager.add_message(
                        session_id,
                        "assistant",
                        f"Error: {gate.error_message}",
                    )
                    collector.finish_span(root_span, status=SpanStatus.ERROR)
                else:
                    final_text = ""
                    has_error = False
                    async for event in executor.execute_stream(prompt, runtime_context):
                        event = {
                            **event,
                            "trace_id": collector.trace_id,
                            "span_id": root_span.span_id,
                        }
                        yield event

                        if event.get("type") == "complete":
                            final_text = event.get("text", "")
                        elif event.get("type") == "error":
                            has_error = True
                            final_text = f"Error: {event.get('message', 'Unknown error')}"

                    if final_text and not has_error:
                        output_guardrail = self._evaluate_output_guardrail(final_text)
                        if output_guardrail and output_guardrail.blocked:
                            failure_class = "output_guardrail_blocked"
                            has_error = True
                            top = output_guardrail.top_decision()
                            blocked_message = (
                                top.message
                                if top is not None
                                else "Output blocked by governance policy."
                            )
                            yield {
                                "type": "error",
                                "message": blocked_message,
                                "guardrail": output_guardrail.to_dict(),
                                "trace_id": collector.trace_id,
                                "span_id": root_span.span_id,
                            }
                            final_text = f"Error: {blocked_message}"

                    if final_text:
                        await self._session_manager.add_message(session_id, "assistant", final_text)

                    if has_error and failure_class is None:
                        failure_class = "execution_error"
                    collector.finish_span(root_span, status=SpanStatus.ERROR if has_error else SpanStatus.OK)
        except Exception as exc:
            failure_class = failure_class or "runtime_exception"
            collector.finish_span(root_span, status=SpanStatus.ERROR)
            yield {
                "type": "error",
                "message": str(exc),
                "trace_id": collector.trace_id,
                "span_id": root_span.span_id,
            }

        await self._persist_trace(
            collector,
            session_id=session_id,
            workflow_id=None,
            scope="execute_stream",
        )
        await self._session_manager.update_session(session_id, {"trace_id": collector.trace_id})
        latency_ms = int((perf_counter() - start) * 1000)
        await self._record_slo(
            scope=scope,
            success=failure_class is None,
            latency_ms=latency_ms,
            failure_class=failure_class,
        )

    # ==================== Workflow ====================

    async def create_workflow(
        self,
        session_id: str,
        task: str,
        workflow_type: str = "graph",
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if self._store is None:
            raise RuntimeError("Service not initialized")

        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        runtime_metadata = dict(metadata or {})
        guardrail_result = self._evaluate_input_guardrail(task, runtime_metadata)
        approval_id: str | None = None
        status = "created"
        if guardrail_result and guardrail_result.blocked:
            top = guardrail_result.top_decision()
            message = top.message if top else "Workflow blocked by governance policy."
            raise ValueError(message)

        if (
            guardrail_result
            and guardrail_result.requires_approval
            and self._hitl_enabled
            and self._approval_manager is not None
        ):
            approval_payload = self._workflow_approval_payload(
                session_id=session_id,
                task=task,
                workflow_type=workflow_type,
            )
            approval = await self._approval_manager.create(
                kind="workflow",
                reason="Workflow requires human approval before execution.",
                payload=approval_payload,
                idempotency_key=idempotency_key,
            )
            approval_id = approval.approval_id
            runtime_metadata["approval_id"] = approval.approval_id
            runtime_metadata["guardrail"] = guardrail_result.to_dict()
            if approval.status != "approved":
                status = "awaiting_approval"

        workflow_id = f"wf-{_utcnow().strftime('%Y%m%d')}-{uuid_hex(8)}"
        now = utc_now_iso()
        payload = {
            "id": workflow_id,
            "session_id": session_id,
            "task": task,
            "workflow_type": workflow_type,
            "status": status,
            "thread_id": f"thread-{workflow_id}",
            "result": None,
            "error": None,
            "trace_id": None,
            "steps": [],
            "handoff_envelopes": [],
            "elapsed_ms": 0,
            "created_at": now,
            "updated_at": now,
            "metadata": runtime_metadata,
            "approval_id": approval_id,
        }

        write_result = await self._store.set(
            workflow_id,
            payload,
            namespace=self.WORKFLOW_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=0,
            idempotency_key=idempotency_key,
        )
        if not write_result.record:
            raise RuntimeError("Failed to persist workflow")

        await self._store.set(
            f"{session_id}:{workflow_id}",
            {
                "workflow_id": workflow_id,
                "session_id": session_id,
                "status": status,
                "updated_at": now,
            },
            namespace=self.TASK_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=0,
            idempotency_key=idempotency_key,
        )

        return write_result.record.value

    async def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        if self._store is None:
            return None
        record = await self._store.get(workflow_id, namespace=self.WORKFLOW_NAMESPACE)
        if not record:
            return None
        return {**record.value, "version": record.version}

    async def start_workflow(self, workflow_id: str, trace_id: str | None = None) -> dict[str, Any]:
        return await self._run_workflow(
            workflow_id,
            require_status={"created", "paused", "failed", "awaiting_approval"},
            trace_id=trace_id,
        )

    async def resume_workflow(self, workflow_id: str, trace_id: str | None = None) -> dict[str, Any]:
        return await self._run_workflow(workflow_id, require_status={"paused"}, trace_id=trace_id)

    async def pause_workflow(self, workflow_id: str) -> dict[str, Any]:
        workflow, record = await self._get_workflow_with_record(workflow_id)
        if not workflow or record is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if workflow["status"] in {"completed", "failed"}:
            raise ValueError(f"Workflow cannot be paused in status: {workflow['status']}")

        workflow["status"] = "paused"
        workflow["updated_at"] = utc_now_iso()

        write = await self._store.set(
            workflow_id,
            workflow,
            namespace=self.WORKFLOW_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=record.version,
        )
        if not write.applied or not write.record:
            raise RuntimeError("Failed to pause workflow due to version conflict")

        await self._store.set(
            f"{workflow['session_id']}:{workflow_id}",
            {
                "workflow_id": workflow_id,
                "session_id": workflow["session_id"],
                "status": "paused",
                "updated_at": workflow["updated_at"],
            },
            namespace=self.TASK_NAMESPACE,
            ttl=self._session_ttl,
        )

        return write.record.value

    # ==================== Trace ====================

    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        if self._store is None:
            return None
        record = await self._store.get(trace_id, namespace=self.TRACE_NAMESPACE)
        if not record:
            return None
        return record.value

    async def list_approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        if self._approval_manager is None:
            return []
        approvals = await self._approval_manager.list(status=status)
        return [approval.to_dict() for approval in approvals]

    async def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        if self._approval_manager is None:
            return None
        approval = await self._approval_manager.get(approval_id)
        if approval is None:
            return None
        return approval.to_dict()

    async def approve_approval(
        self,
        approval_id: str,
        *,
        reviewer: str,
        comment: str | None = None,
    ) -> dict[str, Any] | None:
        if self._approval_manager is None:
            return None
        approval = await self._approval_manager.resolve(
            approval_id,
            approved=True,
            reviewer=reviewer,
            comment=comment,
        )
        if approval is None:
            return None
        return approval.to_dict()

    async def reject_approval(
        self,
        approval_id: str,
        *,
        reviewer: str,
        comment: str | None = None,
    ) -> dict[str, Any] | None:
        if self._approval_manager is None:
            return None
        approval = await self._approval_manager.resolve(
            approval_id,
            approved=False,
            reviewer=reviewer,
            comment=comment,
        )
        if approval is None:
            return None
        return approval.to_dict()

    async def get_slo_dashboard(self) -> dict[str, Any]:
        if self._slo_manager is None:
            return {
                "timestamp": utc_now_iso(),
                "targets": {},
                "by_scope": {},
                "alerts": [],
            }
        return await self._slo_manager.get_snapshot()

    def parse_handoff_payload(self, payload: str) -> dict[str, Any]:
        if self._handoff_protocol is None:
            raise ValueError("handoff protocol not initialized")
        envelope = self._handoff_protocol.parse(payload)
        return envelope.model_dump()

    async def get_stats(self) -> dict[str, Any]:
        session_stats = await self._session_manager.get_stats() if self._session_manager else {}
        workflow_total = 0
        trace_total = 0
        if self._store:
            workflow_total = len(await self._store.list(namespace=self.WORKFLOW_NAMESPACE))
            trace_total = len(await self._store.list(namespace=self.TRACE_NAMESPACE))

        return {
            "workspaces": self._workspace_manager.get_stats() if self._workspace_manager else {},
            "sessions": session_stats,
            "executor_cache_size": len(self._executor_cache),
            "workflows": {"total": workflow_total},
            "traces": {"total": trace_total},
            "store_backend": self._store.__class__.__name__ if self._store else "none",
            "governance": {
                "guardrails_enabled": self._guardrails_enabled,
                "hitl_enabled": self._hitl_enabled,
            },
        }

    # ==================== Internal ====================

    def _should_allow(self, scope: str) -> tuple[bool, str | None]:
        if self._slo_manager is None:
            return True, None
        return self._slo_manager.should_allow(scope)

    async def _record_slo(
        self,
        *,
        scope: str,
        success: bool,
        latency_ms: int,
        failure_class: str | None = None,
        retried: bool = False,
    ) -> None:
        if self._slo_manager is None:
            return
        await self._slo_manager.record(
            scope=scope,
            success=success,
            latency_ms=latency_ms,
            failure_class=failure_class,
            retried=retried,
        )

    def _evaluate_input_guardrail(
        self,
        prompt: str,
        context: dict[str, Any] | None,
    ) -> GuardrailResult | None:
        if not self._guardrails_enabled or self._guardrail_engine is None:
            return None
        return self._guardrail_engine.evaluate_input(prompt, context=context)

    def _evaluate_output_guardrail(self, output_text: str) -> GuardrailResult | None:
        if not self._guardrails_enabled or self._guardrail_engine is None:
            return None
        return self._guardrail_engine.evaluate_output(output_text)

    async def _guard_execution_input(
        self,
        *,
        session: SessionState,
        scope_kind: str,
        prompt: str,
        context: dict[str, Any] | None,
    ) -> _ExecutionGateFailure | None:
        guardrail_result = self._evaluate_input_guardrail(prompt, context)
        if guardrail_result is None:
            return None

        if guardrail_result.blocked:
            top = guardrail_result.top_decision()
            message = top.message if top else "Request blocked by governance policy."
            return _ExecutionGateFailure(
                error_message=message,
                requires_approval=False,
                metadata={
                    "guardrail": guardrail_result.to_dict(),
                    "failure_class": "guardrail_blocked",
                },
            )

        if not (guardrail_result.requires_approval and self._hitl_enabled and self._approval_manager):
            return None

        sanitized_context = {
            key: value
            for key, value in (context or {}).items()
            if key not in {"approval_id", "idempotency_key"}
        }
        payload = {
            "session_id": session.session_id,
            "workspace_id": session.workspace_id,
            "agent_id": session.agent_id,
            "prompt": prompt,
            "context": sanitized_context,
            "scope_kind": scope_kind,
        }
        approval_id = (context or {}).get("approval_id")
        if await self._approval_manager.is_approved(approval_id, kind=scope_kind, payload=payload):
            return None

        approval = await self._approval_manager.create(
            kind=scope_kind,
            reason="Guardrail policy requires human approval for this request.",
            payload=payload,
            idempotency_key=(context or {}).get("idempotency_key"),
        )
        top = guardrail_result.top_decision()
        message = (
            f"{top.message if top else 'Request requires approval.'} "
            f"Provide approval_id={approval.approval_id} after approval."
        )
        return _ExecutionGateFailure(
            error_message=message,
            requires_approval=True,
            metadata={
                "approval_id": approval.approval_id,
                "approval_status": approval.status,
                "requires_approval": True,
                "guardrail": guardrail_result.to_dict(),
                "failure_class": "guardrail_review",
            },
        )

    def _workflow_approval_payload(
        self,
        *,
        session_id: str,
        task: str,
        workflow_type: str,
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "task": task,
            "workflow_type": workflow_type,
        }

    async def _ensure_workflow_approval(self, workflow: dict[str, Any]) -> None:
        if not self._hitl_enabled or self._approval_manager is None:
            return

        approval_id = workflow.get("approval_id") or workflow.get("metadata", {}).get("approval_id")
        if not approval_id:
            return

        approval_payload = self._workflow_approval_payload(
            session_id=workflow["session_id"],
            task=workflow["task"],
            workflow_type=workflow.get("workflow_type", "graph"),
        )
        approved = await self._approval_manager.is_approved(
            approval_id,
            kind="workflow",
            payload=approval_payload,
        )
        if not approved:
            raise ValueError(f"Workflow requires approval: {approval_id}")

    def _build_workflow_handoffs(
        self,
        workflow: dict[str, Any],
        steps: list[dict[str, Any]],
        trace_id: str,
    ) -> list[dict[str, Any]]:
        if self._handoff_protocol is None or not steps:
            return []

        envelopes: list[dict[str, Any]] = []
        for idx, step in enumerate(steps):
            source = str(step.get("node", "unknown"))
            target = str(steps[idx + 1].get("node")) if idx + 1 < len(steps) else "final_output"
            artifacts: list[dict[str, Any]] = []
            output_preview = step.get("output_preview")
            if output_preview:
                artifacts.append({"type": "preview", "content": str(output_preview)})
            envelope = self._handoff_protocol.build_envelope(
                source_agent=source,
                target_agent=target,
                task=str(workflow.get("task", "workflow handoff")),
                context={
                    "workflow_id": workflow.get("id"),
                    "session_id": workflow.get("session_id"),
                    "step_index": idx,
                },
                artifacts=artifacts,
                trace_id=trace_id,
            )
            envelopes.append(envelope.model_dump())
        return envelopes

    async def _bootstrap_session_state(self, session: SessionState) -> None:
        if self._store is None:
            return
        base_payload = {
            "session_id": session.session_id,
            "workspace_id": session.workspace_id,
            "agent_id": session.agent_id,
            "status": "active",
            "created_at": utc_now_iso(),
        }
        await self._store.set(
            f"{session.session_id}:bootstrap",
            base_payload,
            namespace=self.PLAN_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=0,
        )
        await self._store.set(
            f"{session.session_id}:bootstrap",
            base_payload,
            namespace=self.TASK_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=0,
        )

    async def _delete_session_scoped_state(self, session_id: str) -> None:
        if self._store is None:
            return
        for namespace in (self.TASK_NAMESPACE, self.PLAN_NAMESPACE, self.WORKFLOW_NAMESPACE):
            records = await self._store.list(namespace=namespace, prefix=f"{session_id}:")
            for record in records:
                await self._store.delete(record.key, namespace=namespace)

    async def _get_workflow_with_record(self, workflow_id: str) -> tuple[dict[str, Any] | None, StoreRecord | None]:
        if self._store is None:
            return None, None
        record = await self._store.get(workflow_id, namespace=self.WORKFLOW_NAMESPACE)
        if record is None:
            return None, None
        return record.value, record

    async def _run_workflow(
        self,
        workflow_id: str,
        require_status: set[str],
        trace_id: str | None,
    ) -> dict[str, Any]:
        workflow, record = await self._get_workflow_with_record(workflow_id)
        if not workflow or record is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if workflow["status"] not in require_status:
            raise ValueError(f"Workflow status {workflow['status']} does not allow start/resume")

        await self._ensure_workflow_approval(workflow)

        scope = f"workflow:{workflow.get('workflow_type', 'graph')}"
        allowed, reason = self._should_allow(scope)
        if not allowed:
            await self._record_slo(
                scope=scope,
                success=False,
                latency_ms=0,
                failure_class="circuit_open",
            )
            raise ValueError(reason or "workflow circuit open")

        workflow["status"] = "running"
        workflow["updated_at"] = utc_now_iso()
        running_write = await self._store.set(
            workflow_id,
            workflow,
            namespace=self.WORKFLOW_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=record.version,
        )
        if not running_write.applied or not running_write.record:
            raise RuntimeError("Failed to mark workflow running due to version conflict")

        session = await self.get_session(workflow["session_id"])
        if not session:
            raise ValueError(f"Session not found: {workflow['session_id']}")

        start = perf_counter()
        failure_class: str | None = None
        try:
            result_payload = await self._execute_workflow_runtime(workflow, session, trace_id=trace_id)
            workflow["status"] = "completed"
            workflow["result"] = result_payload["result"]
            workflow["error"] = None
            workflow["steps"] = result_payload["steps"]
            workflow["handoff_envelopes"] = result_payload.get("handoff_envelopes", [])
            workflow["elapsed_ms"] = result_payload["elapsed_ms"]
            workflow["trace_id"] = result_payload["trace_id"]
            workflow["updated_at"] = utc_now_iso()
        except Exception as exc:
            workflow["status"] = "failed"
            workflow["error"] = str(exc)
            workflow["handoff_envelopes"] = []
            workflow["updated_at"] = utc_now_iso()
            failure_class = "workflow_runtime_error"

        final_write = await self._store.set(
            workflow_id,
            workflow,
            namespace=self.WORKFLOW_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=running_write.record.version,
        )
        if not final_write.applied or not final_write.record:
            raise RuntimeError("Failed to persist final workflow state")

        await self._store.set(
            f"{workflow['session_id']}:{workflow_id}",
            {
                "workflow_id": workflow_id,
                "session_id": workflow["session_id"],
                "status": workflow["status"],
                "updated_at": workflow["updated_at"],
            },
            namespace=self.TASK_NAMESPACE,
            ttl=self._session_ttl,
        )

        latency_ms = int((perf_counter() - start) * 1000)
        await self._record_slo(
            scope=scope,
            success=workflow["status"] == "completed",
            latency_ms=latency_ms,
            failure_class=failure_class if workflow["status"] != "completed" else None,
        )

        return final_write.record.value

    async def _execute_workflow_runtime(
        self,
        workflow: dict[str, Any],
        session: SessionState,
        *,
        trace_id: str | None,
    ) -> dict[str, Any]:
        executor = await self._ensure_executor_for_session(session)

        collector = self._new_trace_collector(trace_id)
        root_span = collector.start_span(
            "proxy.workflow",
            kind=SpanKind.WORKFLOW,
            attributes={
                "workflow_id": workflow["id"],
                "session_id": workflow["session_id"],
                "workflow_type": workflow.get("workflow_type", "graph"),
            },
        )

        engine_factory = executor.create_engine_factory()
        workflow_type = workflow.get("workflow_type", "graph")

        if workflow_type == "team":
            team = TeamDefinition(
                name=f"wf-{workflow['id']}",
                goal="analysis -> code -> review",
                process=TeamProcess.SEQUENTIAL,
                agents=[
                    AgentRole(name="analysis", role="Analyst", goal="Break down the task", agent_type="explore"),
                    AgentRole(name="implementation", role="Engineer", goal="Implement solution", agent_type="code"),
                    AgentRole(name="review", role="Reviewer", goal="Review and finalize", agent_type="review"),
                ],
            )
            team_executor = TeamExecutor(team=team, checkpointer=self._workflow_checkpointer)
            result = await team_executor.run(
                task=workflow["task"],
                engine_factory=engine_factory,
                thread_id=workflow["thread_id"],
            )
        else:
            graph = self._build_default_workflow(workflow_name=workflow["id"])
            compiled = graph.compile(checkpointer=self._workflow_checkpointer)
            result = await compiled.invoke(
                initial_state={
                    "task": workflow["task"],
                    "input": workflow["task"],
                },
                engine_factory=engine_factory,
                thread_id=workflow["thread_id"],
            )

        collector.finish_span(root_span, status=SpanStatus.OK)
        await self._persist_trace(
            collector,
            session_id=workflow["session_id"],
            workflow_id=workflow["id"],
            scope="workflow",
        )

        steps = [
            {
                "node": step.node,
                "agent_type": step.agent_type,
                "elapsed_ms": step.elapsed_ms,
                "update_keys": step.update_keys,
                "output_preview": step.output_preview,
            }
            for step in result.trace
        ]

        output = self._extract_workflow_output(result.state)
        output_guardrail = self._evaluate_output_guardrail(output)
        if output_guardrail and output_guardrail.blocked:
            top = output_guardrail.top_decision()
            message = top.message if top else "Workflow output blocked by governance policy."
            raise RuntimeError(message)

        handoff_envelopes = self._build_workflow_handoffs(workflow, steps, collector.trace_id)
        return {
            "result": output,
            "steps": steps,
            "handoff_envelopes": handoff_envelopes,
            "elapsed_ms": result.total_elapsed_ms,
            "trace_id": collector.trace_id,
        }

    def _build_default_workflow(self, workflow_name: str) -> WorkflowGraph:
        graph = WorkflowGraph(name=f"workflow-{workflow_name}")
        graph.add_node(
            StepNode(
                name="analysis",
                agent_type="explore",
                output_key="analysis",
                prompt_template=(
                    "Task: {task}\n"
                    "Analyze requirements, risks, and constraints. Output concise bullet points."
                ),
                max_iterations=8,
            )
        )
        graph.add_node(
            StepNode(
                name="implementation",
                agent_type="code",
                output_key="implementation",
                prompt_template=(
                    "Task: {task}\n"
                    "Analysis: {analysis}\n"
                    "Produce implementation details and key decisions."
                ),
                max_iterations=10,
            )
        )
        graph.add_node(
            StepNode(
                name="review",
                agent_type="review",
                output_key="review",
                prompt_template=(
                    "Task: {task}\n"
                    "Analysis: {analysis}\n"
                    "Implementation: {implementation}\n"
                    "Review and provide final output with risks and next steps."
                ),
                max_iterations=6,
            )
        )

        graph.add_edge("analysis", "implementation")
        graph.add_edge("implementation", "review")
        graph.add_edge("review", None)
        return graph

    async def _persist_trace(
        self,
        collector: TraceCollector,
        *,
        session_id: str | None,
        workflow_id: str | None,
        scope: str,
    ) -> None:
        if self._store is None:
            return
        trace_payload = {
            "trace_id": collector.trace_id,
            "scope": scope,
            "session_id": session_id,
            "workflow_id": workflow_id,
            "summary": collector.get_summary(),
            "spans": collector.export_json(),
            "updated_at": utc_now_iso(),
        }
        await self._store.set(
            collector.trace_id,
            trace_payload,
            namespace=self.TRACE_NAMESPACE,
            ttl=self._session_ttl,
        )

    async def _ensure_executor_for_session(self, session: SessionState) -> AgentExecutor:
        executor = self._executor_cache.get(session.session_id)
        if executor and executor._initialized:
            return executor

        if not self._workspace_manager:
            raise RuntimeError("Service not initialized")

        workspace = self._workspace_manager.get_workspace(session.workspace_id)
        if not workspace:
            raise ValueError(f"Workspace not found: {session.workspace_id}")

        saved_config = session.metadata.get("_agent_config") if session.metadata else None
        executor = await self._create_executor(workspace, session.agent_id, config_overrides=saved_config)

        self._executor_cache[session.session_id] = executor
        if self._session_manager:
            self._session_manager.set_executor(session.session_id, executor)

        return executor

    async def _create_executor(
        self,
        workspace: WorkspaceContext,
        agent_id: str,
        config_overrides: dict[str, Any] | None = None,
    ) -> AgentExecutor:
        agent_definition = await self._get_agent_definition(agent_id)
        system_prompt = await self._get_system_prompt(agent_id)

        executor = AgentExecutor(workspace)
        await executor.initialize(agent_definition, system_prompt, config_overrides=config_overrides)
        return executor

    async def _get_agent_definition(self, agent_id: str) -> dict[str, Any]:
        if self._agent_directory:
            agent_info = self._agent_directory.get_agent(agent_id)
            if agent_info:
                return agent_info.metadata

        return {
            "identity": {"name": agent_id, "description": f"Agent: {agent_id}"},
            "model": {"id": "default"},
            "capabilities": {"tools": ["*"]},
            "limits": {},
        }

    async def _get_system_prompt(self, agent_id: str) -> str | None:
        if self._agent_directory:
            agent_info = self._agent_directory.get_agent(agent_id)
            if agent_info and agent_info.system_prompt_path:
                try:
                    return agent_info.system_prompt_path.read_text(encoding="utf-8")
                except Exception as exc:
                    self._logger.warning("Failed to read system prompt: %s", exc)
        return None

    def _new_trace_collector(self, trace_id: str | None = None) -> TraceCollector:
        collector = TraceCollector()
        if trace_id:
            # TraceCollector intentionally keeps trace id private; we allow propagation here.
            collector._trace_id = trace_id  # type: ignore[attr-defined]
        return collector

    @staticmethod
    def _extract_workflow_output(state: dict[str, Any]) -> str:
        for key in ("review", "final_review", "implementation", "analysis"):
            if key in state:
                return str(state[key])
        return str(state)


def utc_now_iso() -> str:
    return _utcnow().isoformat() + "Z"


def uuid_hex(length: int) -> str:
    import uuid

    return uuid.uuid4().hex[:length]
