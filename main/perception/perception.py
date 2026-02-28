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


# 错误严重度级别 → 使用 error_triggers
_ERROR_SEVERITY = frozenset({"error", "critical", "fatal", "crit"})
# 警告严重度级别 → 使用 warn_triggers
_WARN_SEVERITY = frozenset({"warn", "warning"})

# 别名扩展表：用户在 levels 中写 "warn" 时自动覆盖 "warning"，
# 写 "error" 时自动覆盖 "critical"/"fatal"/"crit"，反之亦然。
_LEVEL_ALIAS_GROUPS: list[frozenset[str]] = [
    _ERROR_SEVERITY,
    _WARN_SEVERITY,
]


def _expand_levels(levels: list) -> frozenset[str]:
    """将 levels 列表展开为包含别名的集合（不区分大小写）。"""
    expanded: set[str] = set()
    for raw in levels:
        lvl = str(raw).lower()
        expanded.add(lvl)
        for group in _LEVEL_ALIAS_GROUPS:
            if lvl in group:
                expanded.update(group)
    return frozenset(expanded)


def perceive(
    data: dict | list,
    rules: dict[str, Any] | None = None,
) -> PerceptionResult:
    """
    基于解析后的数据执行感知与决策

    Args:
        data: 解析后的 Python 结构（来自 parse_log）
        rules: 可配置规则，例如：
            {
                "levels": ["error", "warn", "critical"],  # 监听的级别白名单
                "error_triggers": "find_user",            # error/critical/fatal 时的决策
                "warn_triggers": "find_user",             # warn/warning 时的决策
            }

    Returns:
        PerceptionResult 包含决策类型、原因、数据

    Notes:
        levels 白名单中不存在的级别将被跳过，不触发任何决策。
        不在已知严重度分组（_ERROR_SEVERITY / _WARN_SEVERITY）中的自定义级别
        若出现在 levels 白名单内，将保守地使用 error_triggers。
    """
    rules = rules or {}
    # 展开别名后的级别集合，例如 ["warn"] 自动覆盖 "warning"
    levels_set = _expand_levels(rules.get("levels", ["error", "warn"]))
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

        # 跳过不在 levels 白名单中的级别
        if level_lower not in levels_set:
            continue

        if level_lower in _ERROR_SEVERITY:
            decision = _to_decision_type(error_triggers)
            return PerceptionResult(
                decision=decision,
                reason=f"Detected {level_lower} level event: {evt.get('message', evt)}",
                data=evt,
                metadata={"level": level_lower, "rule": "error_triggers"},
            )
        if level_lower in _WARN_SEVERITY:
            decision = _to_decision_type(warn_triggers)
            return PerceptionResult(
                decision=decision,
                reason=f"Detected {level_lower} level event: {evt.get('message', evt)}",
                data=evt,
                metadata={"level": level_lower, "rule": "warn_triggers"},
            )
        # 自定义级别在 levels 白名单内但不属于已知分组 → 保守触发 error_triggers
        decision = _to_decision_type(error_triggers)
        return PerceptionResult(
            decision=decision,
            reason=f"Detected {level_lower} level event: {evt.get('message', evt)}",
            data=evt,
            metadata={"level": level_lower, "rule": "error_triggers"},
        )

    # 默认：无异常，不触发
    return PerceptionResult(
        decision=DecisionType.NONE,
        reason="No actionable events detected",
        data={"events_count": len(events)},
        metadata={"action": "none"},
    )


def _extract_events(data: dict | list) -> list[dict | Any]:
    """
    从解析数据中提取事件列表。

    匹配顺序：
    1. data 本身为列表 → 直接使用
    2. dict 中的已知容器键（events / logs / records / data / items）
    3. 其他情况 → 返回空列表（不猜测语义不明的任意列表字段）
    """
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        for key in ("events", "logs", "records", "data", "items"):
            if key in data and isinstance(data[key], list):
                return data[key]
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
