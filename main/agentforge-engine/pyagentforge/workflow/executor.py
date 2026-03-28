"""
工作流执行器

编译后的 WorkflowGraph 执行器，负责：
- 按图定义遍历节点
- 通过 reducer 合并状态
- 可选 checkpoint 持久化和崩溃恢复
- 执行 trace 记录
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from pyagentforge.kernel.checkpoint import BaseCheckpointer, Checkpoint
from pyagentforge.utils.logging import get_logger
from pyagentforge.workflow.graph import END, EdgeType, StepNode, WorkflowGraph

logger = get_logger(__name__)


@dataclass
class StepTrace:
    """单个节点的执行记录"""

    node: str
    agent_type: str
    elapsed_ms: int
    update_keys: list[str]
    output_preview: str = ""


@dataclass
class WorkflowResult:
    """工作流执行结果"""

    state: dict[str, Any]
    trace: list[StepTrace]
    thread_id: str
    total_elapsed_ms: int
    resumed: bool = False


class WorkflowExecutor:
    """编译后的工作流执行器"""

    def __init__(
        self,
        graph: WorkflowGraph,
        checkpointer: BaseCheckpointer | None = None,
    ) -> None:
        self.graph = graph
        self.checkpointer = checkpointer

        self._edge_map: dict[str, list] = {}
        for edge in graph.edges:
            self._edge_map.setdefault(edge.source, []).append(edge)

    async def invoke(
        self,
        initial_state: dict[str, Any] | None = None,
        engine_factory: Any | None = None,
        thread_id: str | None = None,
    ) -> WorkflowResult:
        """
        执行工作流

        Args:
            initial_state: 初始状态
            engine_factory: EngineFactory 实例，负责创建 AgentEngine
            thread_id: 线程 ID（用于 checkpoint），不提供则自动生成

        Returns:
            WorkflowResult 包含最终状态和执行 trace
        """
        thread_id = thread_id or str(uuid.uuid4())
        state = dict(initial_state or {})
        trace: list[StepTrace] = []
        workflow_start = time.monotonic()
        resumed = False

        resume_node = None
        if self.checkpointer:
            cp = await self.checkpointer.load(thread_id)
            if cp:
                state = cp.context_data.get("state", state)
                resume_node = cp.metadata.get("next_node")
                trace_data = cp.context_data.get("trace", [])
                valid_keys = {"node", "agent_type", "elapsed_ms", "update_keys", "output_preview"}
                trace = [
                    StepTrace(**{k: t[k] for k in valid_keys if k in t})
                    for t in trace_data
                    if isinstance(t, dict) and "node" in t
                ]
                resumed = True
                logger.info(
                    f"Resumed workflow '{self.graph.name}' from node '{resume_node}'",
                    extra_data={"thread_id": thread_id},
                )

        current = resume_node or self.graph.entry_point
        max_steps = sum(n.max_iterations for n in self.graph.nodes.values()) + len(
            self.graph.nodes
        )
        step_count = 0

        while current and current != END:
            step_count += 1
            if step_count > max_steps:
                logger.error("Workflow exceeded maximum step count")
                break

            node = self.graph.nodes.get(current)
            if not node:
                logger.error(f"Node '{current}' not found in graph")
                break

            logger.info(
                f"[Workflow '{self.graph.name}'] Executing node '{current}' ({node.agent_type})"
            )
            step_start = time.monotonic()

            try:
                update = await self._execute_node(node, state, engine_factory)
            except Exception as e:
                elapsed = int((time.monotonic() - step_start) * 1000)
                logger.error(
                    f"[Workflow] Node '{current}' failed: {e}",
                    extra_data={"elapsed_ms": elapsed},
                )
                trace.append(StepTrace(
                    node=current,
                    agent_type=node.agent_type,
                    elapsed_ms=elapsed,
                    update_keys=[],
                    output_preview=f"ERROR: {str(e)[:200]}",
                ))
                state["__error__"] = {"node": current, "error": str(e)}
                break

            elapsed = int((time.monotonic() - step_start) * 1000)

            output_text = str(update.get(node.output_key, ""))[:200] if node.output_key else ""
            step_trace = StepTrace(
                node=current,
                agent_type=node.agent_type,
                elapsed_ms=elapsed,
                update_keys=list(update.keys()),
                output_preview=output_text,
            )
            trace.append(step_trace)

            for key, value in update.items():
                reducer = self.graph.reducers.get(key)
                if reducer:
                    state[key] = reducer(state.get(key), value)
                else:
                    state[key] = value

            next_node = self._resolve_next(current, state)

            if self.checkpointer:
                cp = Checkpoint(
                    session_id=thread_id,
                    iteration=step_count,
                    context_data={
                        "state": state,
                        "trace": [
                            {
                                "node": t.node,
                                "agent_type": t.agent_type,
                                "elapsed_ms": t.elapsed_ms,
                                "update_keys": t.update_keys,
                                "output_preview": t.output_preview,
                            }
                            for t in trace
                        ],
                    },
                    metadata={
                        "workflow": self.graph.name,
                        "next_node": next_node,
                        "completed_node": current,
                    },
                )
                await self.checkpointer.save(thread_id, cp)

            logger.info(
                f"[Workflow] Node '{current}' done in {elapsed}ms → next='{next_node or END}'"
            )
            current = next_node

        completed_normally = "__error__" not in state
        if self.checkpointer and completed_normally:
            await self.checkpointer.delete(thread_id)

        total_elapsed = int((time.monotonic() - workflow_start) * 1000)

        return WorkflowResult(
            state=state,
            trace=trace,
            thread_id=thread_id,
            total_elapsed_ms=total_elapsed,
            resumed=resumed,
        )

    async def _execute_node(
        self,
        node: StepNode,
        state: dict[str, Any],
        engine_factory: Any | None,
    ) -> dict[str, Any]:
        """执行单个节点，返回 state 的 partial update"""
        prompt = node.build_prompt(state)

        if engine_factory is None:
            return {
                node.output_key or node.name: f"[dry-run] Node '{node.name}' would execute: {prompt[:100]}"
            }

        engine = engine_factory.create(
            agent_type=node.agent_type,
            system_prompt=node.system_prompt,
            tools=node.tools,
            max_iterations=node.max_iterations,
        )

        result = await engine.run(prompt)

        update: dict[str, Any] = {}
        if node.output_key:
            update[node.output_key] = result
        update["messages"] = [
            {"role": "step", "name": node.name, "content": result[:500]}
        ]
        return update

    def _resolve_next(
        self, current: str, state: dict[str, Any]
    ) -> str | None:
        """根据边定义和当前状态确定下一个节点"""
        edges = self._edge_map.get(current, [])
        if not edges:
            return None

        for edge in edges:
            if edge.edge_type == EdgeType.NORMAL:
                return edge.target if edge.target != END else None

            if edge.edge_type == EdgeType.CONDITIONAL and edge.condition_fn:
                try:
                    result = edge.condition_fn(state)
                except Exception as e:
                    logger.error(f"Condition function error at '{current}': {e}")
                    return None

                if edge.routes:
                    target = edge.routes.get(result)
                    if target == END or target is None:
                        return None
                    return target

        return None
