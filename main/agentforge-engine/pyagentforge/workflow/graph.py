"""
声明式工作流图

提供 LangGraph 风格的图编排能力：StepNode / Edge / ConditionalEdge，
编译为 WorkflowExecutor 后可带 checkpoint 执行。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

END = "__END__"

StateReducer = Callable[[Any, Any], Any]


def append_reducer(existing: Any, new: Any) -> list:
    """追加式 reducer：将新值追加到列表中。"""
    result = list(existing) if existing else []
    if isinstance(new, list):
        result.extend(new)
    else:
        result.append(new)
    return result


def last_write_wins(_existing: Any, new: Any) -> Any:
    """覆盖式 reducer：新值直接覆盖旧值。"""
    return new


class EdgeType(StrEnum):
    NORMAL = "normal"
    CONDITIONAL = "conditional"


@dataclass
class Edge:
    """工作流中的边"""
    source: str
    target: str | None = None
    edge_type: EdgeType = EdgeType.NORMAL
    condition_fn: Callable[[dict[str, Any]], str] | None = None
    routes: dict[str, str | None] | None = None


@dataclass
class StepNode:
    """工作流中的节点——封装一次 AgentEngine 执行"""

    name: str
    agent_type: str = "explore"
    system_prompt: str | None = None
    tools: list[str] | str = "*"
    max_iterations: int = 20
    output_key: str | None = None
    prompt_template: str | None = None

    def build_prompt(self, state: dict[str, Any]) -> str:
        """根据模板和 state 生成发给子引擎的 prompt"""
        if self.prompt_template:
            try:
                return self.prompt_template.format(**state)
            except KeyError:
                return self.prompt_template
        task = state.get("task", state.get("input", ""))
        return str(task)


class WorkflowGraph:
    """
    声明式工作流图

    用法::

        wf = WorkflowGraph("review-flow")
        wf.add_node(StepNode(name="analyze", agent_type="explore"))
        wf.add_node(StepNode(name="implement", agent_type="code"))
        wf.add_node(StepNode(name="review", agent_type="review"))
        wf.add_edge("analyze", "implement")
        wf.add_edge("implement", "review")
        wf.add_conditional_edge("review", check_fn, {"pass": END, "fail": "implement"})
        executor = wf.compile()
    """

    def __init__(
        self,
        name: str,
        *,
        reducers: dict[str, StateReducer] | None = None,
    ) -> None:
        self.name = name
        self.nodes: dict[str, StepNode] = {}
        self.edges: list[Edge] = []
        self.entry_point: str | None = None
        self.reducers: dict[str, StateReducer] = {
            "messages": append_reducer,
            "decisions": append_reducer,
            "trace": append_reducer,
            **(reducers or {}),
        }

    # ── 图构建 API ──────────────────────────────────────────

    def add_node(self, node: StepNode) -> WorkflowGraph:
        if node.name in self.nodes:
            raise ValueError(f"Duplicate node name: {node.name}")
        self.nodes[node.name] = node
        if self.entry_point is None:
            self.entry_point = node.name
        return self

    def add_edge(self, source: str, target: str | None) -> WorkflowGraph:
        self.edges.append(Edge(source=source, target=target))
        return self

    def add_conditional_edge(
        self,
        source: str,
        condition_fn: Callable[[dict[str, Any]], str],
        routes: dict[str, str | None],
    ) -> WorkflowGraph:
        self.edges.append(
            Edge(
                source=source,
                target=None,
                edge_type=EdgeType.CONDITIONAL,
                condition_fn=condition_fn,
                routes=routes,
            )
        )
        return self

    def set_entry(self, name: str) -> WorkflowGraph:
        if name not in self.nodes:
            raise ValueError(f"Node not found: {name}")
        self.entry_point = name
        return self

    # ── 编译 ────────────────────────────────────────────────

    def compile(
        self,
        checkpointer: Any | None = None,
    ) -> WorkflowExecutor:
        """编译图为可执行的 WorkflowExecutor"""
        from pyagentforge.workflow.executor import WorkflowExecutor

        self._validate()
        return WorkflowExecutor(graph=self, checkpointer=checkpointer)

    def _validate(self) -> None:
        if not self.entry_point or self.entry_point not in self.nodes:
            raise ValueError(f"Invalid entry point: {self.entry_point}")

        edge_sources = {e.source for e in self.edges}
        for source in edge_sources:
            if source not in self.nodes:
                raise ValueError(f"Edge source '{source}' not in nodes")

        for edge in self.edges:
            if edge.edge_type == EdgeType.NORMAL and edge.target:
                if edge.target not in self.nodes and edge.target != END:
                    raise ValueError(
                        f"Edge target '{edge.target}' not in nodes"
                    )
            if edge.edge_type == EdgeType.CONDITIONAL and edge.routes:
                for route_target in edge.routes.values():
                    if (
                        route_target
                        and route_target != END
                        and route_target not in self.nodes
                    ):
                        raise ValueError(
                            f"Conditional route target '{route_target}' not in nodes"
                        )

    # ── 可视化 ──────────────────────────────────────────────

    def to_mermaid(self) -> str:
        """导出为 Mermaid 图定义"""
        lines = ["graph TD"]
        for name, node in self.nodes.items():
            label = f"{name}[{name}\\n({node.agent_type})]"
            lines.append(f"    {label}")
        for edge in self.edges:
            if edge.edge_type == EdgeType.NORMAL:
                target = edge.target or END
                lines.append(f"    {edge.source} --> {target}")
            elif edge.edge_type == EdgeType.CONDITIONAL and edge.routes:
                for label, target in edge.routes.items():
                    target = target or END
                    lines.append(f"    {edge.source} -->|{label}| {target}")
        return "\n".join(lines)
