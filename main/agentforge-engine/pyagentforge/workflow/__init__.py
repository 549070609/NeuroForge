"""
PyAgentForge Workflow — 声明式工作流编排 + 团队协作 + Handoff + Tracing

包含：
- WorkflowGraph / StepNode / WorkflowExecutor — 图编排
- HandoffPayload / HandoffManager — Agent 间上下文传递
- AgentRole / TeamDefinition / TeamExecutor — 团队协作
- TraceCollector / Span — 结构化可观测性
"""

from pyagentforge.workflow.executor import (
    StepTrace,
    WorkflowExecutor,
    WorkflowResult,
)
from pyagentforge.workflow.factory import EngineFactory
from pyagentforge.workflow.graph import (
    END,
    EdgeType,
    StepNode,
    WorkflowGraph,
    append_reducer,
    last_write_wins,
)
from pyagentforge.workflow.handoff import (
    HandoffManager,
    HandoffPayload,
)
from pyagentforge.workflow.team import (
    AgentRole,
    TeamDefinition,
    TeamExecutor,
    TeamProcess,
)
from pyagentforge.workflow.tracing import (
    Span,
    SpanKind,
    SpanStatus,
    TraceCollector,
    TracingPlugin,
)

__all__ = [
    # Graph
    "END",
    "EdgeType",
    "EngineFactory",
    "StepNode",
    "StepTrace",
    "WorkflowExecutor",
    "WorkflowGraph",
    "WorkflowResult",
    "append_reducer",
    "last_write_wins",
    # Handoff
    "HandoffManager",
    "HandoffPayload",
    # Team
    "AgentRole",
    "TeamDefinition",
    "TeamExecutor",
    "TeamProcess",
    # Tracing
    "Span",
    "SpanKind",
    "SpanStatus",
    "TraceCollector",
    "TracingPlugin",
]
