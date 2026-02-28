"""
Active Agent Handler

Implements a proactive agent that monitors battlefield data via the perception
pipeline, automatically detects threats, and initiates conversations with the user.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mock_cod_tool import (
    AVAILABLE_SCENARIOS,
    generate_batch,
    generate_scenario,
)
from ws_manager import ConnectionManager

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = {
    "parse_log": {
        "name": "parse_log",
        "description": "解析战场通信日志",
        "parameters": {"raw_data": "string", "format": "string"},
    },
    "perceive": {
        "name": "perceive",
        "description": "感知和分析日志数据，识别威胁级别",
        "parameters": {"data": "object", "rules": "object"},
    },
    "threat_analysis": {
        "name": "threat_analysis",
        "description": "对检测到的威胁进行深度分析",
        "parameters": {"threat_data": "object"},
    },
    "situation_report": {
        "name": "situation_report",
        "description": "生成战场态势综合报告",
        "parameters": {"events": "array"},
    },
    "generate_mock_data": {
        "name": "generate_mock_data",
        "description": "生成模拟战场日志数据",
        "parameters": {"scenario": "string", "count": "integer"},
    },
    "situation_compare": {
        "name": "situation_compare",
        "description": "调取态势流式数据进行比对分析",
        "parameters": {"snapshot": "object"},
    },
}


def perceive_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Simplified perception logic — mirrors main/perception/perception.py behavior.
    Scans events for threat levels and decides on action.
    """
    critical = [e for e in events if e.get("level") == "CRITICAL"]
    warnings = [e for e in events if e.get("level") == "WARNING"]
    info = [e for e in events if e.get("level") == "INFO"]

    if critical:
        return {
            "decision": "FIND_USER",
            "priority": "CRITICAL",
            "reason": f"检测到 {len(critical)} 个关键威胁事件",
            "trigger_events": critical,
            "summary": {
                "critical_count": len(critical),
                "warning_count": len(warnings),
                "info_count": len(info),
                "total": len(events),
            },
        }
    elif warnings:
        return {
            "decision": "FIND_USER",
            "priority": "WARNING",
            "reason": f"检测到 {len(warnings)} 个警告事件需要关注",
            "trigger_events": warnings,
            "summary": {
                "critical_count": 0,
                "warning_count": len(warnings),
                "info_count": len(info),
                "total": len(events),
            },
        }
    else:
        return {
            "decision": "NONE",
            "priority": "INFO",
            "reason": "所有事件正常，无需干预",
            "trigger_events": [],
            "summary": {
                "critical_count": 0,
                "warning_count": 0,
                "info_count": len(info),
                "total": len(events),
            },
        }



async def trigger_mock_data(
    manager: ConnectionManager,
    session_id: str,
    scenario: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """
    Trigger mock battlefield data generation and push log events + perception.

    Returns (generated_events, perception_result_if_actionable).
    The caller is responsible for generating and sending proactive alert messages
    (via LLM summarization or template fallback).

    Aborts early if the session has no live WebSocket connections.
    """
    if scenario and scenario in AVAILABLE_SCENARIOS:
        events = generate_scenario(scenario)
    else:
        events = generate_batch(count=20)

    for event in events:
        sent = await manager.send_to_session(session_id, {
            "type": "log_event",
            "data": event,
        })
        if sent == 0:
            logger.warning(
                "No active connections for session %s, aborting mock data push",
                session_id,
            )
            return events, None
        await asyncio.sleep(0.3)

    perception = perceive_events(events)

    await manager.send_to_session(session_id, {
        "type": "tool_call",
        "tool": "perceive",
        "description": "感知和分析日志数据，识别威胁级别",
        "status": "executing",
    })
    await asyncio.sleep(0.5)

    await manager.send_to_session(session_id, {
        "type": "tool_result",
        "tool": "perceive",
        "result": perception,
        "status": "completed",
    })

    if perception["decision"] == "FIND_USER":
        return events, perception
    return events, None


def get_tool_list() -> list[dict[str, Any]]:
    return list(TOOL_DEFINITIONS.values())
