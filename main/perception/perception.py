"""
感知与决策逻辑

解析后的数据 -> 内部事件 -> 决策（找用户 / 自己执行 / 调用其它 Agent）
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DecisionType(str, Enum):
    """决策类型"""
    FIND_USER = "find_user"      # 找用户对话/通知
    EXECUTE = "execute"          # 自己执行
    CALL_AGENT = "call_agent"    # 调用其它 Agent
    NONE = "none"               # 无动作


@dataclass
class PerceptionResult:
    """感知结果"""
    decision: DecisionType
    reason: str
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None


def perceive(
    data: dict | list,
    rules: dict[str, Any] | None = None,
) -> PerceptionResult:
    """
    基于解析后的数据执行感知与决策

    Args:
        data: 解析后的 Python 结构（来自 parse_log）
        rules: 可配置规则，如 {"error_triggers": "find_user", "levels": ["error", "warn"]}

    Returns:
        PerceptionResult 包含决策类型、原因、数据
    """
    rules = rules or {}
    levels = rules.get("levels", ["error", "warn"])
    error_triggers = rules.get("error_triggers", "find_user")
    warn_triggers = rules.get("warn_triggers", "find_user")

    # 扁平化提取事件列表
    events = _extract_events(data)

    # 规则匹配
    for event in events:
        evt = event if isinstance(event, dict) else {}
        level = _get_level(evt)
        if not level:
            continue

        level_lower = str(level).lower()
        if level_lower == "error":
            decision = _to_decision_type(error_triggers)
            return PerceptionResult(
                decision=decision,
                reason=f"Detected error level event: {evt.get('message', evt)}",
                data=evt,
                metadata={"level": "error", "rule": "error_triggers"},
            )
        if level_lower in ("warn", "warning"):
            decision = _to_decision_type(warn_triggers)
            return PerceptionResult(
                decision=decision,
                reason=f"Detected warn level event: {evt.get('message', evt)}",
                data=evt,
                metadata={"level": "warn", "rule": "warn_triggers"},
            )

    # 默认：无异常，不触发
    return PerceptionResult(
        decision=DecisionType.NONE,
        reason="No actionable events detected",
        data={"events_count": len(events)},
        metadata={"action": "none"},
    )


def _extract_events(data: dict | list) -> list[dict | Any]:
    """从解析数据中提取事件列表"""
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        # 常见键名
        for key in ("events", "logs", "records", "data", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
        # 取第一个列表类型的值
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


def _to_decision_type(value: str) -> DecisionType:
    """将字符串转换为 DecisionType"""
    s = str(value).lower()
    for dt in DecisionType:
        if dt.value == s:
            return dt
    return DecisionType.FIND_USER


def _get_level(evt: dict) -> str | None:
    """从事件中提取 level 字段"""
    for key in ("level", "severity", "log_level", "type"):
        if key in evt and evt[key]:
            return str(evt[key])
    return None
