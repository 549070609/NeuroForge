"""
结构化 Trace/Span 可观测性

为 AgentEngine 和 WorkflowExecutor 提供结构化执行追踪，
无外部依赖（不依赖 OpenTelemetry），但数据格式兼容 OTel 导出。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SpanKind(StrEnum):
    WORKFLOW = "workflow"
    AGENT = "agent"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    HANDOFF = "handoff"


class SpanStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Span:
    """执行追踪的基本单元"""

    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    parent_span_id: str | None = None
    name: str = ""
    kind: SpanKind = SpanKind.AGENT
    status: SpanStatus = SpanStatus.OK
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        if self.end_time <= 0:
            return int((time.time() - self.start_time) * 1000)
        return int((self.end_time - self.start_time) * 1000)

    def finish(self, status: SpanStatus = SpanStatus.OK) -> None:
        self.end_time = time.time()
        self.status = status

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
        }


class TraceCollector:
    """收集和管理执行 trace

    用法::

        collector = TraceCollector()
        span = collector.start_span("agent.run", kind=SpanKind.AGENT)
        # ... do work ...
        span.finish()
        print(collector.get_summary())
    """

    def __init__(self, max_spans: int = 10000) -> None:
        self._trace_id = uuid.uuid4().hex[:32]
        self._spans: list[Span] = []
        self._active_spans: dict[str, Span] = {}
        self._max_spans = max_spans

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.AGENT,
        parent: Span | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """开始一个新的 span"""
        span = Span(
            trace_id=self._trace_id,
            parent_span_id=parent.span_id if parent else None,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )
        self._active_spans[span.span_id] = span
        return span

    def finish_span(
        self,
        span: Span,
        status: SpanStatus = SpanStatus.OK,
    ) -> None:
        """结束一个 span"""
        span.finish(status)
        self._active_spans.pop(span.span_id, None)
        self._spans.append(span)
        if len(self._spans) > self._max_spans:
            self._spans = self._spans[-self._max_spans // 2 :]

    def get_spans(self) -> list[Span]:
        return list(self._spans)

    def get_active_spans(self) -> list[Span]:
        return list(self._active_spans.values())

    def get_summary(self) -> dict[str, Any]:
        """生成 trace 摘要"""
        by_kind: dict[str, list[int]] = {}
        errors = 0

        for span in self._spans:
            kind = span.kind.value
            by_kind.setdefault(kind, []).append(span.duration_ms)
            if span.status == SpanStatus.ERROR:
                errors += 1

        summary: dict[str, Any] = {
            "trace_id": self._trace_id,
            "total_spans": len(self._spans),
            "active_spans": len(self._active_spans),
            "errors": errors,
            "by_kind": {},
        }
        for kind, durations in by_kind.items():
            summary["by_kind"][kind] = {
                "count": len(durations),
                "total_ms": sum(durations),
                "avg_ms": sum(durations) // len(durations) if durations else 0,
                "max_ms": max(durations) if durations else 0,
            }
        return summary

    def export_json(self) -> list[dict[str, Any]]:
        """导出所有 span 为 JSON 兼容格式"""
        return [s.to_dict() for s in self._spans]

    def clear(self) -> None:
        self._spans.clear()
        self._active_spans.clear()
        self._trace_id = uuid.uuid4().hex[:32]


class TracingPlugin:
    """通过 Hook 系统集成 TraceCollector 的插件式接口

    这不是正式的 Plugin 子类（避免循环依赖），
    而是提供 hook 回调函数供 PluginManager 注册。
    """

    def __init__(self) -> None:
        self.collector = TraceCollector()
        self._current_agent_span: Span | None = None
        self._current_llm_span: Span | None = None

    def on_engine_start(self, engine: Any) -> None:
        if self._current_agent_span:
            self.collector.finish_span(self._current_agent_span, SpanStatus.CANCELLED)
        self._current_agent_span = self.collector.start_span(
            f"agent.run:{getattr(engine, '_session_id', 'unknown')}",
            kind=SpanKind.AGENT,
            attributes={"model": getattr(engine.provider, "model", "unknown")},
        )

    def on_before_llm_call(self, messages: Any) -> None:
        self._current_llm_span = self.collector.start_span(
            "llm.call",
            kind=SpanKind.LLM_CALL,
            parent=self._current_agent_span,
            attributes={"message_count": len(messages) if isinstance(messages, list) else 0},
        )

    def on_after_llm_call(self, response: Any) -> None:
        if self._current_llm_span:
            self._current_llm_span.set_attribute(
                "stop_reason",
                getattr(response, "stop_reason", "unknown"),
            )
            self._current_llm_span.set_attribute(
                "has_tool_calls",
                getattr(response, "has_tool_calls", False),
            )
            self.collector.finish_span(self._current_llm_span)
            self._current_llm_span = None

    def on_task_complete(self, result: Any) -> None:
        if self._current_agent_span:
            self._current_agent_span.set_attribute(
                "result_length",
                len(str(result)) if result else 0,
            )
            self.collector.finish_span(self._current_agent_span)
            self._current_agent_span = None
