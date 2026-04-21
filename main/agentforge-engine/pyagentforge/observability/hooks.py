"""
Observability Hooks (P0-6)

提供一个可作为 `plugin_manager` 传入 `AgentEngine` 的 hook 收集器，
把引擎钩子转换为 metrics 调用：

  on_engine_start     → 开始 agent.run 计时
  on_before_llm_call  → 开始 llm.call 计时
  on_after_llm_call   → llm_tokens_total + llm_latency_seconds
  on_task_complete    → agent.run 计时结束

工具调用 metrics 可通过 `ToolExecutor` 直接调用 `collector.observe(...)`
"""

from __future__ import annotations

import time
from typing import Any

from pyagentforge.observability.metrics import (
    MetricsCollector,
    get_collector,
)


class ObservabilityHooks:
    """作为 `plugin_manager` 替身，实现 `emit_hook(name, *args)` 协议。"""

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self.collector = collector or get_collector()
        self._llm_start: dict[int, float] = {}
        self._run_start: dict[int, float] = {}

    async def emit_hook(self, hook_name: str, *args: Any) -> list[Any]:
        """分派到对应 handler；始终返回空列表（不修改参数）。"""
        handler = getattr(self, f"_h_{hook_name}", None)
        if handler is not None:
            try:
                handler(*args)
            except Exception:
                # 可观测性失败不应影响主流程
                pass
        return []

    # ── handlers ──────────────────────────────────────────────

    def _h_on_engine_start(self, engine: Any) -> None:
        self._run_start[id(engine)] = time.perf_counter()

    def _h_on_before_llm_call(self, messages: Any) -> None:
        self._llm_start[id(messages)] = time.perf_counter()

    def _h_on_after_llm_call(self, response: Any) -> None:
        # 尽量从 response 拿 model / usage 信息
        model = getattr(response, "model", "") or ""
        usage = getattr(response, "usage", None)

        # 尝试匹配最近一次 before_llm_call 的时间戳
        if self._llm_start:
            _id, start = self._llm_start.popitem()
            duration = time.perf_counter() - start
            self.collector.observe(
                "llm_latency_seconds", duration, model=model
            )

        # llm tokens（如果 response 包含 usage）
        if usage is not None:
            for token_type in ("input_tokens", "output_tokens"):
                count = getattr(usage, token_type, None)
                if isinstance(count, (int, float)) and count > 0:
                    self.collector.inc(
                        "llm_tokens_total",
                        float(count),
                        model=model,
                        type=token_type,
                    )

        # 每次 LLM 调用视为一次 iteration 完成
        self.collector.inc("agent_iterations_total")

    def _h_on_task_complete(self, text: str) -> None:
        # 记录 agent.run 总时长（best-effort：匹配任一活动 engine）
        if self._run_start:
            _id, start = self._run_start.popitem()
            duration = time.perf_counter() - start
            self.collector.observe("agent_run_duration_seconds", duration)
