"""
主动感知器 Tools

供 Agent 调用的 BaseTool 实现
"""

import json
import re
from pathlib import Path
from typing import Any

from pyagentforge.kernel.base_tool import BaseTool

try:
    from .parser import parse_log
    from .perception import perceive, PerceptionResult, DecisionType
    from .executor import DecisionExecutor, execute_decision, ExecutionResult
except ImportError:
    from parser import parse_log
    from perception import perceive, PerceptionResult, DecisionType
    from executor import DecisionExecutor, execute_decision, ExecutionResult


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
                "description": "Optional rules: levels, error_triggers, warn_triggers",
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
    ) -> str:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            merged_rules = {**self.default_rules, **(rules or {})}
            result = perceive(data, merged_rules)
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
                "description": "Optional perceive rules: levels, error_triggers, warn_triggers",
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
    ) -> str:
        try:
            if isinstance(data, str):
                data = json.loads(data)
            merged_rules = {**self.default_rules, **(rules or {})}
            result = perceive(data, merged_rules)
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
    return (
        f"Decision: {r.decision.value}\n"
        f"Reason: {r.reason}\n"
        f"Data: {r.data}\n"
        f"Metadata: {r.metadata or {}}"
    )
