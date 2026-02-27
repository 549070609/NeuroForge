"""
Active Agent Handler

Implements a proactive agent that monitors battlefield data via the perception
pipeline, automatically detects threats, and initiates conversations with the user.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

from mock_cod_tool import (
    AVAILABLE_SCENARIOS,
    generate_batch,
    generate_scenario,
    generate_single_event,
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


def generate_proactive_message(perception_result: dict[str, Any]) -> str:
    """Generate a proactive agent message based on perception results (template fallback)."""
    priority = perception_result["priority"]
    triggers = perception_result["trigger_events"]
    summary = perception_result["summary"]

    rows = "\n".join(
        f"| {'🔴' if e.get('level') == 'CRITICAL' else '🟡'} {e.get('level', '?')} "
        f"| {e.get('event_type', '?')} "
        f"| {e.get('message', '')[:50]} "
        f"| {e.get('location', '-')} |"
        for e in triggers[:5]
    )

    stat_line = f"🔴×{summary['critical_count']} 🟡×{summary['warning_count']} 🟢×{summary['info_count']} · 共{summary['total']}事件"

    if priority == "CRITICAL":
        return (
            f"**🔴 紧急威胁** · {stat_line}\n\n"
            f"| 级别 | 类型 | 事件 | 位置 |\n"
            f"| --- | --- | --- | --- |\n"
            f"{rows}\n\n"
            f"→ 建议立即评估并授权应对"
        )
    elif priority == "WARNING":
        return (
            f"**🟡 态势警告** · {stat_line}\n\n"
            f"| 级别 | 类型 | 事件 | 位置 |\n"
            f"| --- | --- | --- | --- |\n"
            f"{rows}\n\n"
            f"→ 态势可控，建议保持警戒"
        )
    return ""


def generate_proactive_summary(perception_result: dict[str, Any]) -> str:
    """Generate a concise one-line summary for a proactive message."""
    priority = perception_result["priority"]
    triggers = perception_result["trigger_events"]
    summary = perception_result["summary"]

    event_types = list({e.get("event_type", "未知") for e in triggers[:2]})
    types_str = "、".join(event_types) if event_types else "异常事件"

    if priority == "CRITICAL":
        return (
            f"[紧急] 检测到{summary['critical_count']}个关键威胁"
            f"（{types_str}），需立即响应"
        )
    elif priority == "WARNING":
        return (
            f"[警告] {summary['warning_count']}个警告事件"
            f"（{types_str}），建议关注"
        )
    return f"[通知] 态势正常，{summary['info_count']}个常规事件"


def generate_threat_analysis(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a detailed threat analysis for critical events."""
    critical = [e for e in events if e.get("level") == "CRITICAL"]
    if not critical:
        critical = [e for e in events if e.get("level") == "WARNING"]

    target = critical[0] if critical else events[0]
    threat_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    responses = [
        "建议派遣快速反应部队",
        "请求空中火力支援",
        "启动防御协议 Bravo",
        "立即组织战术撤退",
        "加强区域巡逻频率",
    ]

    return {
        "tool": "threat_analysis",
        "result": {
            "threat_id": f"THR-{random.randint(1000, 9999)}",
            "classification": target.get("event_type", "UNKNOWN"),
            "threat_level": random.choice(threat_levels[1:]),
            "source_event": target.get("message", ""),
            "location": target.get("location", "Unknown"),
            "estimated_hostiles": random.randint(5, 50),
            "confidence": round(random.uniform(0.75, 0.98), 2),
            "recommended_action": random.choice(responses),
            "eta_response": f"{random.randint(3, 15)} 分钟",
        },
    }


def generate_sitrep(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a situation report."""
    critical = [e for e in events if e.get("level") == "CRITICAL"]
    warnings = [e for e in events if e.get("level") == "WARNING"]

    sectors_affected = list({e.get("metadata", {}).get("sector_id", "S-??") for e in events})
    callsigns_active = list({e.get("callsign", "Unknown") for e in events})

    status_options = ["GREEN - 安全", "YELLOW - 警戒", "ORANGE - 紧张", "RED - 危险"]
    if critical:
        overall = status_options[3]
    elif warnings:
        overall = status_options[2] if len(warnings) > 2 else status_options[1]
    else:
        overall = status_options[0]

    return {
        "tool": "situation_report",
        "result": {
            "report_id": f"SITREP-{int(time.time())}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "overall_status": overall,
            "event_summary": {
                "critical": len(critical),
                "warning": len(warnings),
                "info": len(events) - len(critical) - len(warnings),
                "total": len(events),
            },
            "sectors_affected": sectors_affected[:5],
            "active_callsigns": callsigns_active[:5],
            "key_events": [
                {"level": e["level"], "message": e["message"]}
                for e in (critical + warnings)[:5]
            ],
            "recommendation": "保持高度警戒" if critical else "继续常规监控",
        },
    }


async def handle_active_message(message: str, session_events: list[dict]) -> list[dict[str, Any]]:
    """
    Handle a user message in the active agent context.
    The user might ask follow-up questions about detected threats.
    """
    events: list[dict[str, Any]] = []
    msg = message.lower()

    if any(k in msg for k in ["分析", "威胁", "threat", "analysis", "详细"]):
        events.append({
            "type": "tool_call",
            "tool": "threat_analysis",
            "description": "威胁深度分析",
            "status": "executing",
        })
        await asyncio.sleep(0.4)

        analysis = generate_threat_analysis(session_events or [generate_single_event("CRITICAL")])
        events.append({
            "type": "tool_result",
            "tool": "threat_analysis",
            "result": analysis["result"],
            "status": "completed",
        })

        r = analysis["result"]
        events.append({
            "type": "agent_reply",
            "content": (
                f"🎯 **威胁分析** · {r['threat_id']}\n\n"
                f"| 指标 | 值 |\n"
                f"| --- | --- |\n"
                f"| 分类 | **{r['classification']}** |\n"
                f"| 级别 | **{r['threat_level']}** |\n"
                f"| 位置 | {r['location']} |\n"
                f"| 预估兵力 | ~{r['estimated_hostiles']}人 |\n"
                f"| 置信度 | {r['confidence']} |\n"
                f"| 响应时间 | {r['eta_response']} |\n\n"
                f"→ **建议:** {r['recommended_action']}\n\n"
                f"是否批准执行？"
            ),
        })
    elif any(k in msg for k in ["报告", "态势", "sitrep", "situation", "状态"]):
        events.append({
            "type": "tool_call",
            "tool": "situation_report",
            "description": "战场态势报告",
            "status": "executing",
        })
        await asyncio.sleep(0.4)

        sitrep = generate_sitrep(session_events or [generate_single_event()])
        events.append({
            "type": "tool_result",
            "tool": "situation_report",
            "result": sitrep["result"],
            "status": "completed",
        })

        r = sitrep["result"]
        s = r["event_summary"]
        key_rows = "\n".join(
            f"| {'🔴' if e['level'] == 'CRITICAL' else '🟡'} {e['level']} | {e['message'][:45]} |"
            for e in r["key_events"]
        )
        events.append({
            "type": "agent_reply",
            "content": (
                f"📊 **态势报告** · {r['overall_status']}\n\n"
                f"| 统计 | 数量 |\n"
                f"| --- | --- |\n"
                f"| 🔴 关键 | {s['critical']} |\n"
                f"| 🟡 警告 | {s['warning']} |\n"
                f"| 🟢 正常 | {s['info']} |\n"
                f"| **合计** | **{s['total']}** |\n\n"
                f"| 级别 | 关键事件 |\n"
                f"| --- | --- |\n"
                f"{key_rows}\n\n"
                f"**区域:** {', '.join(r['sectors_affected'])} · "
                f"**单位:** {', '.join(r['active_callsigns'])}\n\n"
                f"→ {r['recommendation']}"
            ),
        })
    elif any(k in msg for k in ["批准", "执行", "approve", "go ahead", "确认"]):
        events.append({
            "type": "agent_reply",
            "content": (
                "✅ **授权确认** · 指令已下达\n\n"
                "| 单位 | 任务 | 状态 |\n"
                "| --- | --- | --- |\n"
                "| Bravo-6 | 战术展开 | ✅ 已确认 |\n"
                "| Eagle Eye | 空中监视 | ✅ 已确认 |\n"
                "| Warhammer | 火力待命 | ✅ 已确认 |\n\n"
                "各单位就位，持续监控中。"
            ),
        })
    else:
        events.append({
            "type": "agent_reply",
            "content": (
                "收到。可用指令：\n\n"
                "| 指令 | 说明 |\n"
                "| --- | --- |\n"
                "| **威胁分析** | 深度分析当前威胁 |\n"
                "| **态势报告** | 战场综合报告 |\n"
                "| **批准执行** | 授权应对方案 |"
            ),
        })

    return events


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
