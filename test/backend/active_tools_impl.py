"""
Active Agent Tool Implementations

BaseTool subclasses that back the active (Overwatch) agent's capabilities.
These tools are registered with the AgentEngine so the LLM can actually call them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ENGINE_PATH = str(Path(__file__).resolve().parents[2] / "main" / "agentforge-engine")
if ENGINE_PATH not in sys.path:
    sys.path.insert(0, ENGINE_PATH)

from pyagentforge.kernel.base_tool import BaseTool


# ---------------------------------------------------------------------------
# PerceiveTool
# ---------------------------------------------------------------------------


class PerceiveTool(BaseTool):
    """Analyze a list of battlefield events and classify threat level."""

    name = "perceive"
    description = (
        "分析战场事件列表，识别威胁等级（CRITICAL / WARNING / INFO），"
        "决定是否需要向指挥官上报。返回决策、优先级和关键事件摘要。"
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "description": "战场事件列表，每条含 level、event_type、message 等字段",
                "items": {"type": "object"},
            }
        },
        "required": ["events"],
    }

    async def execute(self, events: list[dict] | None = None, **kwargs: Any) -> str:  # type: ignore[override]
        from active_handler import perceive_events

        if events is None:
            events = []
        result = perceive_events(events)
        return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# ThreatAnalysisTool
# ---------------------------------------------------------------------------

_THREAT_TACTICS: dict[str, list[str]] = {
    "PERIMETER_BREACH": ["立即加强周界防御", "通知备战分队", "实施主动巡逻"],
    "AMBUSH": ["建立交叉火力阵地", "请求空中掩护", "规划撤退路线"],
    "COMMS_DISRUPTED": ["切换备用频道", "部署通信中继", "启动静默协议"],
    "AA_THREAT": ["低空飞行规避", "暂停空中资产使用", "请求压制火力"],
    "ENEMY_MASSING": ["实施预防性炮击", "请求增援", "加强侦察"],
    "IED_WARNING": ["禁止车辆通行", "通知爆炸物处置分队", "绕道行进"],
}

_LEVEL_URGENCY: dict[str, str] = {
    "CRITICAL": "需要立即采取行动（≤5 分钟）",
    "WARNING": "需要尽快处置（≤30 分钟）",
    "INFO": "例行监控，无须立即行动",
}


class ThreatAnalysisTool(BaseTool):
    """Deep analysis of a specific threat with tactical recommendations."""

    name = "threat_analysis"
    description = "对特定战场威胁进行深度分析，输出评估等级、战术建议和优先行动清单。"
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "event_type": {"type": "string", "description": "威胁类型（如 AMBUSH、IED_WARNING）"},
            "level": {"type": "string", "description": "威胁等级：CRITICAL / WARNING / INFO"},
            "message": {"type": "string", "description": "事件描述文本"},
            "location": {"type": "string", "description": "位置信息（可选）"},
        },
        "required": ["event_type", "level", "message"],
    }

    async def execute(  # type: ignore[override]
        self,
        event_type: str = "",
        level: str = "INFO",
        message: str = "",
        location: str = "",
        **kwargs: Any,
    ) -> str:
        recommendations = _THREAT_TACTICS.get(event_type, ["实施标准应急程序", "保持战备状态"])
        urgency = _LEVEL_URGENCY.get(level, "例行监控")

        result = {
            "threat_type": event_type,
            "level": level,
            "urgency": urgency,
            "location": location or "未指定",
            "message": message,
            "recommendations": recommendations,
            "priority_actions": recommendations[:2],
        }
        return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# SituationReportTool
# ---------------------------------------------------------------------------


class SituationReportTool(BaseTool):
    """Generate a structured battlefield situation report from event list."""

    name = "situation_report"
    description = (
        "基于战场事件列表生成结构化态势报告，包含威胁分布统计、"
        "关键事件清单和整体威胁评级。"
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "description": "战场事件列表",
                "items": {"type": "object"},
            }
        },
        "required": ["events"],
    }

    async def execute(self, events: list[dict] | None = None, **kwargs: Any) -> str:  # type: ignore[override]
        if events is None:
            events = []

        critical = [e for e in events if e.get("level") == "CRITICAL"]
        warnings = [e for e in events if e.get("level") == "WARNING"]
        info = [e for e in events if e.get("level") == "INFO"]

        overall = "CRITICAL" if critical else ("WARNING" if warnings else "NORMAL")

        report = {
            "overall_threat_level": overall,
            "stats": {
                "critical": len(critical),
                "warning": len(warnings),
                "info": len(info),
                "total": len(events),
            },
            "critical_events": [
                {
                    "event_type": e.get("event_type", "?"),
                    "message": e.get("message", ""),
                    "location": e.get("location", ""),
                }
                for e in critical[:5]
            ],
            "warning_events": [
                {
                    "event_type": e.get("event_type", "?"),
                    "message": e.get("message", ""),
                    "location": e.get("location", ""),
                }
                for e in warnings[:5]
            ],
        }
        return json.dumps(report, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# SituationCompareTool
# ---------------------------------------------------------------------------


class SituationCompareTool(BaseTool):
    """Compare and analyze a battlefield situation snapshot."""

    name = "situation_compare"
    description = (
        "接收战场态势统计数据和最近事件列表，进行比对分析，"
        "返回威胁演变趋势、事件分布和重点关注项。"
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "stats": {
                "type": "object",
                "description": "事件级别统计 {critical: N, warning: N, info: N, total: N}",
                "properties": {
                    "critical": {"type": "integer"},
                    "warning": {"type": "integer"},
                    "info": {"type": "integer"},
                    "total": {"type": "integer"},
                },
            },
            "recent_events": {
                "type": "array",
                "description": "最近战场事件列表（含 level、event_type、message、location）",
                "items": {"type": "object"},
            },
        },
        "required": [],
    }

    async def execute(  # type: ignore[override]
        self,
        stats: dict | None = None,
        recent_events: list[dict] | None = None,
        **kwargs: Any,
    ) -> str:
        stats = stats or {}
        recent_events = recent_events or []

        critical_count = stats.get("critical", 0)
        warning_count = stats.get("warning", 0)
        info_count = stats.get("info", 0)
        total_count = stats.get("total", 0)

        threat_level = (
            "CRITICAL" if critical_count > 0 else ("WARNING" if warning_count > 0 else "NORMAL")
        )
        critical_ratio = round(critical_count / total_count, 3) if total_count > 0 else 0.0
        warning_ratio = round(warning_count / total_count, 3) if total_count > 0 else 0.0

        critical_events = [e for e in recent_events if e.get("level") == "CRITICAL"]
        warning_events = [e for e in recent_events if e.get("level") == "WARNING"]

        result = {
            "stats": stats,
            "analysis": {
                "overall_threat_level": threat_level,
                "critical_ratio": critical_ratio,
                "warning_ratio": warning_ratio,
                "trend": (
                    "威胁上升" if critical_ratio > 0.3 else
                    ("威胁平稳" if critical_ratio > 0 else "态势平稳")
                ),
            },
            "critical_events": [
                {
                    "event_type": e.get("event_type", "?"),
                    "message": e.get("message", ""),
                    "location": e.get("location", ""),
                }
                for e in critical_events[:5]
            ],
            "warning_events": [
                {
                    "event_type": e.get("event_type", "?"),
                    "message": e.get("message", ""),
                    "location": e.get("location", ""),
                }
                for e in warning_events[:5]
            ],
            "events_analyzed": len(recent_events),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# GenerateMockDataTool
# ---------------------------------------------------------------------------


class GenerateMockDataTool(BaseTool):
    """Generate simulated battlefield event data for demo / testing."""

    name = "generate_mock_data"
    description = (
        "生成模拟战场事件数据。支持指定场景（伏击/空袭/侦察/补给）或随机生成。"
        "用于演示和测试感知能力。"
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "scenario": {
                "type": "string",
                "description": "场景类型：ambush / air_strike / recon / supply_run / random",
                "enum": ["ambush", "air_strike", "recon", "supply_run", "random"],
            },
            "count": {
                "type": "integer",
                "description": "生成事件数量（仅 random 模式有效，默认 5）",
                "default": 5,
            },
        },
        "required": [],
    }

    async def execute(  # type: ignore[override]
        self,
        scenario: str = "random",
        count: int = 5,
        **kwargs: Any,
    ) -> str:
        from mock_cod_tool import AVAILABLE_SCENARIOS, generate_batch, generate_scenario

        if scenario and scenario != "random" and scenario in AVAILABLE_SCENARIOS:
            events = generate_scenario(scenario)
        else:
            events = generate_batch(count=min(count, 50))

        return json.dumps(events, ensure_ascii=False, indent=2)
