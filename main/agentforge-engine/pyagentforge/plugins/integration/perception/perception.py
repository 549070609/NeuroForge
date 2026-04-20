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
    triggered_events: list[dict[str, Any]] | None = None  # 聚合模式下携带所有触发事件


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
    aggregate: bool = False,
) -> PerceptionResult:
    """
    基于解析后的数据执行感知与决策

    Args:
        data:      解析后的 Python 结构（来自 parse_log）
        rules:     可配置规则，例如：
                     levels          - 监听级别白名单，默认 ["error", "warn"]
                     error_triggers  - error/critical/fatal 时的决策，默认 "find_user"
                     warn_triggers   - warn/warning 时的决策，默认 "find_user"
                     max_events      - 聚合模式下最多处理事件数，默认 50
        aggregate: False（默认）= 首匹配即返回（向后兼容）
                   True          = 聚合批次内所有触发事件后统一决策

    Returns:
        PerceptionResult：
            - 非聚合模式：triggered_events=None，与原行为完全一致
            - 聚合模式：triggered_events 含所有触发事件列表，
                        data 含 {triggered_count, highest_severity, error_count, warn_count}

    Notes:
        levels 白名单中不存在的级别将被跳过，不触发任何决策。
        不在已知严重度分组（_ERROR_SEVERITY / _WARN_SEVERITY）中的自定义级别
        若出现在 levels 白名单内，将保守地使用 error_triggers。
    """
    rules = rules or {}
    levels_set     = _expand_levels(rules.get("levels", ["error", "warn"]))
    error_triggers = rules.get("error_triggers", "find_user")
    warn_triggers  = rules.get("warn_triggers",  "find_user")
    max_events     = int(rules.get("max_events", 50))

    events = _extract_events(data)

    # ── 非聚合路径（原逻辑，完全不变）────────────────────────────────────────
    if not aggregate:
        for event in events:
            evt = event if isinstance(event, dict) else {}
            level = _get_level(evt)
            if not level:
                continue
            level_lower = str(level).lower()
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
        return PerceptionResult(
            decision=DecisionType.NONE,
            reason="No actionable events detected",
            data={"events_count": len(events)},
            metadata={"action": "none"},
        )

    # ── 聚合路径（新增）────────────────────────────────────────────────────────
    # 严重度权重：error > warn > custom（数字越大越高）
    _SEVERITY_WEIGHT = {"error": 2, "warn": 1, "custom": 0}

    triggered: list[dict[str, Any]] = []
    highest_weight   = -1
    highest_severity = "custom"

    for event in events[:max_events]:
        evt = event if isinstance(event, dict) else {}
        level = _get_level(evt)
        if not level:
            continue
        level_lower = str(level).lower()
        if level_lower not in levels_set:
            continue

        triggered.append({"_level_normalized": level_lower, **evt})

        if level_lower in _ERROR_SEVERITY:
            w = _SEVERITY_WEIGHT["error"]
        elif level_lower in _WARN_SEVERITY:
            w = _SEVERITY_WEIGHT["warn"]
        else:
            w = _SEVERITY_WEIGHT["custom"]

        if w > highest_weight:
            highest_weight   = w
            highest_severity = (
                "error" if level_lower in _ERROR_SEVERITY
                else "warn" if level_lower in _WARN_SEVERITY
                else level_lower
            )

    if not triggered:
        return PerceptionResult(
            decision=DecisionType.NONE,
            reason="No actionable events detected",
            data={"events_count": len(events)},
            metadata={"action": "none", "aggregate": True},
            triggered_events=[],
        )

    if highest_weight == _SEVERITY_WEIGHT["error"]:
        decision = _to_decision_type(error_triggers)
        rule     = "error_triggers"
    elif highest_weight == _SEVERITY_WEIGHT["warn"]:
        decision = _to_decision_type(warn_triggers)
        rule     = "warn_triggers"
    else:
        decision = _to_decision_type(error_triggers)
        rule     = "error_triggers"

    error_count = sum(1 for e in triggered if e.get("_level_normalized") in _ERROR_SEVERITY)
    warn_count  = sum(1 for e in triggered if e.get("_level_normalized") in _WARN_SEVERITY)

    return PerceptionResult(
        decision=decision,
        reason=(
            f"Aggregated {len(triggered)} event(s): "
            f"{error_count} error, {warn_count} warn — highest: {highest_severity}"
        ),
        data={
            "triggered_count":   len(triggered),
            "highest_severity":  highest_severity,
            "error_count":       error_count,
            "warn_count":        warn_count,
            "total_events_seen": len(events),
        },
        metadata={"rule": rule, "aggregate": True},
        triggered_events=triggered,
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
