"""
主动感知器 Tools

供 Agent 调用的 BaseTool 实现
"""

import json
import re
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool

from .executor import DecisionExecutor, ExecutionResult, execute_decision
from .parser import parse_log
from .perception import DecisionType, PerceptionResult, perceive
from .strategy import (
    MergeMode,
    StrategyController,
    StrategyResult,
    StrategyType,
    build_controller_from_config,
)


class ParseLogTool(BaseTool):
    """解析 ATON/TOON 格式日志"""

    name = "parse_log"
    description = """Parse ATON or TOON format log text into Python structure.

Input: raw log text (ATON or TOON format)
Output: JSON-serialized dict or list
Format is auto-detected, or specify fmt='aton' or fmt='toon'
Raises on unrecognized format or parse failure.
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "raw": {
                "type": "string",
                "description": "Raw log text in ATON or TOON format",
            },
            "fmt": {
                "type": "string",
                "enum": ["aton", "toon"],
                "description": "Explicit format (optional, auto-detect if omitted)",
            },
            "strict": {
                "type": "boolean",
                "description": "Enable strict parsing mode for TOON (rejects minor format deviations). Default false.",
                "default": False,
            },
        },
        "required": ["raw"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(self, raw: str, fmt: str | None = None, strict: bool = False) -> str:
        result = parse_log(raw, fmt, strict=strict)
        return json.dumps(result, ensure_ascii=False, indent=2)


class PerceiveTool(BaseTool):
    """感知并决策：基于解析后的日志数据"""

    name = "perceive"
    description = """Perceive parsed log data and make decision.

Decision types: find_user (notify user), execute (self-execute), call_agent (delegate)
Uses configurable rules (error_triggers, warn_triggers, levels)
Set aggregate=true to collect all triggered events in a batch instead of stopping at the first match.
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "description": "Parsed log data (dict or list from parse_log)",
            },
            "rules": {
                "type": "object",
                "description": "Optional rules: levels, error_triggers, warn_triggers, max_events",
            },
            "aggregate": {
                "type": "boolean",
                "description": (
                    "If true, collect all triggered events and decide based on highest severity. "
                    "Default false (first-match, backward-compatible)."
                ),
                "default": False,
            },
        },
        "required": ["data"],
    }
    timeout = 10
    risk_level = "low"

    def __init__(self, default_rules: dict[str, Any] | None = None):
        super().__init__()
        self.default_rules = default_rules or {}

    async def execute(
        self,
        data: dict | list | str,
        rules: dict[str, Any] | None = None,
        aggregate: bool = False,
    ) -> str:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            merged_rules = {**self.default_rules, **(rules or {})}
            result = perceive(data, merged_rules, aggregate=aggregate)
            return _format_perception_result(result)
        except Exception as e:
            return f"Perceive failed: {e}"


class ExecuteDecisionTool(BaseTool):
    """感知并执行决策：parse → perceive → execute(find_user|execute|call_agent)"""

    name = "execute_decision"
    description = """Execute perception decision from parsed log data.

Runs: perceive(data) -> then executes based on decision:
- find_user: notify via EventBus/callback
- execute: run configured shell/HTTP actions
- call_agent: delegate to target agent via engine
Requires executor to be wired with engine/event_bus/config.
Set aggregate=true to process all events in a batch (recommended for multi-event payloads).
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "description": "Parsed log data (dict or list from parse_log)",
            },
            "rules": {
                "type": "object",
                "description": "Optional perceive rules: levels, error_triggers, warn_triggers, max_events",
            },
            "aggregate": {
                "type": "boolean",
                "description": (
                    "If true, collect all triggered events and decide based on highest severity. "
                    "Default false (first-match, backward-compatible)."
                ),
                "default": False,
            },
        },
        "required": ["data"],
    }
    timeout = 60
    risk_level = "medium"

    def __init__(
        self,
        default_rules: dict[str, Any] | None = None,
        executor: DecisionExecutor | None = None,
    ):
        super().__init__()
        self.default_rules = default_rules or {}
        self._executor = executor

    def set_executor(self, executor: DecisionExecutor) -> None:
        """注入执行器（由插件在 on_engine_start 时设置）"""
        self._executor = executor

    async def execute(
        self,
        data: dict | list | str,
        rules: dict[str, Any] | None = None,
        aggregate: bool = False,
    ) -> str:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            merged_rules = {**self.default_rules, **(rules or {})}
            result = perceive(data, merged_rules, aggregate=aggregate)
            if result.decision == DecisionType.NONE:
                return _format_perception_result(result) + "\n[No execution: decision=none]"
            if not self._executor:
                return (
                    _format_perception_result(result)
                    + "\n[Execution skipped: no executor configured. Set executor in plugin.]"
                )
            exec_result = await self._executor.execute(result)
            return (
                _format_perception_result(result)
                + f"\n--- Execution ---\nSuccess: {exec_result.success}\nMessage: {exec_result.message}"
            )
        except Exception as e:
            return f"Execute decision failed: {e}"


class StrategyPerceiveTool(BaseTool):
    """多策略感知：同时应用 rule / agent / script 策略，合并后返回决策"""

    name = "strategy_perceive"
    description = """Apply multiple perception strategies simultaneously and merge results.

Strategy types: rule (rule-based), agent (AI agent), script (Python script/callable)
Merge modes:
  - highest_priority: winner is the highest-priority strategy that triggered (default)
  - highest_severity: winner is the result with the highest decision weight
  - all: aggregate all triggered strategy results
Set parallel=true to run all strategies concurrently (default).
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "description": "Parsed log data (dict or list from parse_log)",
            },
            "strategies": {
                "type": "array",
                "description": (
                    "List of strategy configs. Each item: "
                    "{name, type (rule/agent/script), enabled, priority, ...type-specific fields}. "
                    "Rule extra: rules (dict). Script extra: script_path (str). "
                    "Agent extra: prompt (str)."
                ),
                "items": {"type": "object"},
            },
            "merge_mode": {
                "type": "string",
                "enum": ["highest_priority", "highest_severity", "all"],
                "description": "How to merge results from multiple strategies. Default: highest_priority.",
                "default": "highest_priority",
            },
            "parallel": {
                "type": "boolean",
                "description": "Run strategies concurrently. Default true.",
                "default": True,
            },
        },
        "required": ["data"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(
        self,
        default_strategies: list[dict[str, Any]] | None = None,
        default_merge_mode: str = "highest_priority",
        controller: StrategyController | None = None,
    ) -> None:
        super().__init__()
        self._default_strategies = default_strategies or []
        self._default_merge_mode = default_merge_mode
        self._controller         = controller

    def set_controller(self, controller: StrategyController) -> None:
        """注入预构建控制器（由插件在 on_engine_start 时调用）"""
        self._controller = controller

    async def execute(
        self,
        data:       dict | list | str,
        strategies: list[dict[str, Any]] | None = None,
        merge_mode: str  = "highest_priority",
        parallel:   bool = True,
    ) -> str:
        try:
            if isinstance(data, str):
                data = json.loads(data)

            # 优先使用注入的控制器；否则按请求参数即时构建
            if self._controller and not strategies:
                controller = self._controller
            else:
                merged_strategies = strategies or self._default_strategies
                if not merged_strategies:
                    return "StrategyPerceiveTool: no strategies configured"
                controller = build_controller_from_config(
                    merged_strategies,
                    merge_mode=merge_mode or self._default_merge_mode,
                    parallel=parallel,
                )

            merged, details = await controller.apply_all(data)
            return _format_strategy_result(merged, details)
        except Exception as exc:
            return f"StrategyPerceive failed: {exc}"


class ReadLogsTool(BaseTool):
    """从路径读取日志（筛选工具）"""

    name = "read_logs"
    description = """Read log files from path with optional filter.

Supports: path (file or dir), pattern (glob), level_filter (regex), max_lines
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Log file or directory path",
                "default": "./logs",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern for files, e.g. *.toon, *.aton",
                "default": "*",
            },
            "level_filter": {
                "type": "string",
                "description": "Regex to filter lines by level (e.g. error|warn)",
            },
            "max_lines": {
                "type": "integer",
                "description": "Max lines to read per file",
                "default": 1000,
            },
        },
        "required": [],
    }
    timeout = 60
    risk_level = "low"

    def __init__(self, default_path: str = "./logs"):
        super().__init__()
        self.default_path = default_path

    async def execute(
        self,
        path: str | None = None,
        pattern: str = "*",
        level_filter: str | None = None,
        max_lines: int = 1000,
    ) -> str:
        base = Path(path or self.default_path)
        if not base.exists():
            return f"Path not found: {base}"

        lines: list[str] = []
        pattern_re = re.compile(level_filter) if level_filter else None
        truncated_files = 0

        if base.is_file():
            lines.extend(_read_file(base, pattern_re, max_lines))
        else:
            all_files = [f for f in sorted(base.glob(pattern)) if f.is_file()]
            truncated_files = max(0, len(all_files) - 50)
            for f in all_files[:50]:
                lines.extend(_read_file(f, pattern_re, max_lines))

        if not lines:
            return "No matching log content"

        result = "\n".join(lines)
        if truncated_files:
            result += (
                f"\n\n[Warning: File limit reached — showing first 50 of "
                f"{50 + truncated_files} matched files; {truncated_files} file(s) omitted]"
            )
        return result


def _read_file(
    path: Path,
    level_re: re.Pattern | None,
    max_lines: int,
) -> list[str]:
    result = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if len(result) >= max_lines:
                    break
                if level_re is None or level_re.search(line):
                    result.append(line.rstrip())
    except OSError:
        pass
    return result


def _format_perception_result(r: PerceptionResult) -> str:
    lines = [
        f"Decision: {r.decision.value}",
        f"Reason: {r.reason}",
        f"Data: {r.data}",
        f"Metadata: {r.metadata or {}}",
    ]
    if r.triggered_events is not None:
        lines.append(f"Triggered events: {len(r.triggered_events)}")
    return "\n".join(lines)


def _format_strategy_result(
    merged:  PerceptionResult,
    details: list[StrategyResult],
) -> str:
    lines = [
        "=== Strategy Perception Result ===",
        f"Decision:  {merged.decision.value}",
        f"Reason:    {merged.reason}",
        f"Data:      {merged.data}",
        f"Metadata:  {merged.metadata or {}}",
    ]
    if merged.triggered_events is not None:
        lines.append(f"Events:    {len(merged.triggered_events)}")

    if details:
        lines.append("\n--- Per-Strategy Details ---")
        for sr in details:
            status = f"ERROR({sr.error})" if sr.error else sr.result.decision.value
            lines.append(
                f"  [{sr.strategy_type.value}] {sr.strategy_name}: {status}"
                f" — {sr.result.reason[:80]}"
            )
    return "\n".join(lines)
