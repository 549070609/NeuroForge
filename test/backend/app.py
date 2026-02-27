"""
Agent Demo Backend Server

FastAPI application providing WebSocket-based chat for passive and active agents,
mock data generation, tool capability demonstration, and real LLM integration.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from active_handler import (
    AVAILABLE_SCENARIOS,
    generate_proactive_message,
    generate_proactive_summary,
    get_tool_list as active_tools,
    handle_active_message,
    trigger_mock_data,
)
from config_store import ConfigStore
from llm_provider import LLMBridge, get_bridge_from_config
from passive_handler import get_tool_list as passive_tools, handle_passive_message
from ws_manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="NeuroForge Agent Demo", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

passive_manager = ConnectionManager()
active_manager = ConnectionManager()

active_session_events: dict[str, list[dict[str, Any]]] = {}
active_session_alerts: dict[str, list[str]] = {}
session_histories: dict[str, list[dict[str, Any]]] = {}

MAX_SESSION_EVENTS = 200
MAX_SESSION_ALERTS = 50

# Per-session auto-monitor tasks
_monitor_tasks: dict[str, asyncio.Task] = {}
MONITOR_INTERVAL_SECONDS = 15

# Sessions that have already received the welcome message (survives reconnects)
_welcomed_sessions: set[str] = set()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class TriggerMockRequest(BaseModel):
    session_id: str
    scenario: str | None = None


class ConfigUpdateRequest(BaseModel):
    mode: str | None = None
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


PASSIVE_SYSTEM_PROMPT = """你是一个高效的编程与写作助手。你擅长：
1. 根据需求生成高质量代码（Python、JavaScript、TypeScript 等）
2. 审查代码质量并给出改进建议
3. 撰写技术文档、README、API 文档
4. 对长文本进行精炼摘要
5. 在不同格式间转换内容

请用中文回复。当用户请求代码时，直接给出代码和简要说明。"""

ACTIVE_SYSTEM_PROMPT = """你是代号 Overwatch 的战场感知 Agent，向指挥官报告关键情报。

格式要求：
- 军事通信风格，简洁精准，直接给结论和建议
- 不输出解释性废话，不重复已知信息
- 用 🔴🟡🟢 标记威胁级别
- 优先使用 Markdown 表格呈现结构化数据（事件列表、威胁详情、状态统计等）
- 表格之外仅保留一行结论/建议
- 用中文回复

输出示例格式：
**🔴 态势标题** · 统计摘要

| 指标 | 值 |
| --- | --- |
| 字段1 | 数据1 |
| 字段2 | 数据2 |

→ 一句话结论或行动建议"""


def _cleanup_active_session(session_id: str) -> None:
    """Remove in-memory state for an active session.

    Preserves ``_welcomed_sessions`` so that reconnecting clients do not
    receive the welcome message a second time.  Session IDs are per-page-load
    UUIDs, so the set stays bounded.
    """
    active_session_events.pop(session_id, None)
    active_session_alerts.pop(session_id, None)
    session_histories.pop(f"active-{session_id}", None)


def _trim_session_data(session_id: str) -> None:
    """Keep session data within size limits to prevent unbounded growth."""
    evts = active_session_events.get(session_id)
    if evts and len(evts) > MAX_SESSION_EVENTS:
        active_session_events[session_id] = evts[-MAX_SESSION_EVENTS:]

    alerts = active_session_alerts.get(session_id)
    if alerts and len(alerts) > MAX_SESSION_ALERTS:
        active_session_alerts[session_id] = alerts[-MAX_SESSION_ALERTS:]


def _cancel_monitor(session_id: str) -> None:
    """Cancel any running monitor task for the session."""
    task = _monitor_tasks.pop(session_id, None)
    if task and not task.done():
        task.cancel()


MONITOR_DISCONNECT_TIMEOUT_S = 60


async def _run_auto_monitor(session_id: str, scenario: str | None) -> None:
    """
    Continuously push mock battlefield data to a session at a fixed interval.

    Runs until cancelled (stop_monitor received) or no connections remain for
    longer than ``MONITOR_DISCONNECT_TIMEOUT_S``.  Pauses gracefully while no
    WebSocket connections are present so that reconnecting clients automatically
    resume the event stream without a race condition.
    """
    logger.info("Auto monitor started: session=%s scenario=%s", session_id, scenario)

    await active_manager.send_to_session(session_id, {
        "type": "thinking",
        "content": "Overwatch 监控系统激活，正在扫描战场态势...",
    })

    disconnect_since: float | None = None

    try:
        while True:
            if not active_manager.has_connections(session_id):
                if disconnect_since is None:
                    disconnect_since = time.monotonic()
                elif time.monotonic() - disconnect_since > MONITOR_DISCONNECT_TIMEOUT_S:
                    logger.info(
                        "Auto monitor: no connections for %ds, stopping: session=%s",
                        MONITOR_DISCONNECT_TIMEOUT_S,
                        session_id,
                    )
                    break
                await asyncio.sleep(2)
                continue

            disconnect_since = None

            events, perception = await trigger_mock_data(active_manager, session_id, scenario)

            if events:
                active_session_events.setdefault(session_id, []).extend(events)
                _trim_session_data(session_id)

                if perception and active_manager.has_connections(session_id):
                    await _send_proactive_alert(
                        session_id, events, perception, show_thinking=True,
                    )

            await asyncio.sleep(MONITOR_INTERVAL_SECONDS)

    except asyncio.CancelledError:
        logger.info("Auto monitor cancelled: session=%s", session_id)
    except Exception as e:
        logger.error("Auto monitor error session=%s: %s", session_id, e)
    finally:
        # Only remove from tracking if this task is still the registered one.
        # A newer start_monitor may have already replaced it in _monitor_tasks.
        current_task = asyncio.current_task()
        if _monitor_tasks.get(session_id) is current_task:
            _monitor_tasks.pop(session_id, None)
        if not active_manager.has_connections(session_id):
            _cleanup_active_session(session_id)


# ==================== Config Endpoints ====================


@app.get("/api/config")
async def get_config():
    store = ConfigStore.get()
    return store.get_safe_config()


@app.put("/api/config")
async def update_config(req: ConfigUpdateRequest):
    store = ConfigStore.get()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    return store.update(updates)


class TestConnectionRequest(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


@app.post("/api/config/test")
async def test_connection(req: TestConnectionRequest | None = None):
    """Test LLM connection. Uses request body values if provided, else saved config."""
    store = ConfigStore.get()
    provider = (req and req.provider) or store.provider
    api_key = (req and req.api_key) or store.api_key
    model = (req and req.model) or store.model
    base_url = (req and req.base_url) or store.base_url

    if not api_key:
        return {"success": False, "error": "API Key 未配置"}

    bridge = LLMBridge(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=0.3,
        max_tokens=256,
    )
    result = await bridge.test_connection()
    return result


@app.get("/api/config/models")
async def list_models(provider: str = "anthropic"):
    return {"models": ConfigStore.get_models_for_provider(provider)}


# ==================== REST Endpoints ====================


@app.get("/api/health")
async def health():
    store = ConfigStore.get()
    return {
        "status": "ok",
        "service": "agent-demo",
        "mode": "llm" if store.is_llm_mode else "mock",
        "model": store.model if store.is_llm_mode else "mock",
    }


@app.post("/api/chat/passive")
async def chat_passive(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    events = await _handle_passive(sid, req.message)
    return {"events": events, "session_id": sid}


@app.post("/api/active/trigger-mock")
async def trigger_mock(req: TriggerMockRequest):
    events, perception = await trigger_mock_data(active_manager, req.session_id, req.scenario)
    active_session_events.setdefault(req.session_id, []).extend(events)
    if perception:
        await _send_proactive_alert(req.session_id, events, perception)
    return {
        "status": "triggered",
        "event_count": len(events),
        "session_id": req.session_id,
    }


@app.get("/api/tools/passive")
async def list_passive_tools():
    return {"tools": passive_tools()}


@app.get("/api/tools/active")
async def list_active_tools():
    return {"tools": active_tools()}


@app.get("/api/scenarios")
async def list_scenarios():
    return {"scenarios": AVAILABLE_SCENARIOS}


@app.post("/api/session/create")
async def create_session():
    sid = str(uuid.uuid4())
    return {"session_id": sid}


# ==================== LLM Chat Logic ====================


async def _handle_passive(session_id: str, message: str) -> list[dict[str, Any]]:
    """Handle passive agent message — use real LLM if configured, else mock."""
    bridge = get_bridge_from_config()
    if bridge is None:
        return await handle_passive_message(message)

    history = session_histories.setdefault(f"passive-{session_id}", [])
    history.append({"role": "user", "content": message})

    events: list[dict[str, Any]] = []

    try:
        t0 = time.monotonic()
        result = await bridge.chat(
            system_prompt=PASSIVE_SYSTEM_PROMPT,
            messages=history[-20:],
        )
        elapsed = time.monotonic() - t0
        logger.info("Passive LLM call took %.2fs (model=%s)", elapsed, bridge.model)

        reply = result["text"]
        history.append({"role": "assistant", "content": reply})

        usage = result.get("usage", {})
        events.append({
            "type": "tool_result",
            "tool": "llm_call",
            "result": {
                "model": bridge.model,
                "elapsed_s": round(elapsed, 2),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
            "status": "completed",
        })
        events.append({"type": "agent_reply", "content": reply})
    except Exception as e:
        events.append({"type": "agent_reply", "content": f"LLM 调用失败: {e}\n\n已回退到 Mock 模式。"})
        mock_events = await handle_passive_message(message)
        events.extend(mock_events)

    return events


async def _handle_active(session_id: str, message: str, battlefield_events: list[dict]) -> list[dict[str, Any]]:
    """Handle active agent message — use real LLM if configured, else mock."""
    bridge = get_bridge_from_config()
    if bridge is None:
        return await handle_active_message(message, battlefield_events)

    history = session_histories.setdefault(f"active-{session_id}", [])

    context_parts: list[str] = []

    if battlefield_events:
        for evt in battlefield_events[-8:]:
            context_parts.append(f"[{evt.get('level', '?')}] {evt.get('message', '')}")

    context = "\n".join(context_parts) if context_parts else ""

    user_msg = message
    if context:
        user_msg = f"战场数据:\n{context}\n\n指令: {message}"
    history.append({"role": "user", "content": user_msg})

    events: list[dict[str, Any]] = []
    try:
        t0 = time.monotonic()
        result = await bridge.chat(
            system_prompt=ACTIVE_SYSTEM_PROMPT,
            messages=history[-20:],
        )
        elapsed = time.monotonic() - t0
        logger.info("Active LLM call took %.2fs (model=%s)", elapsed, bridge.model)

        reply = result["text"]
        history.append({"role": "assistant", "content": reply})

        events.append({"type": "agent_reply", "content": reply})
    except Exception as e:
        events.append({"type": "agent_reply", "content": f"LLM 调用失败: {e}\n\n已回退到 Mock 模式。"})
        mock_events = await handle_active_message(message, battlefield_events)
        events.extend(mock_events)

    return events


async def _handle_active_proactive(session_id: str, battlefield_events: list[dict]) -> str | None:
    """Generate LLM-summarized proactive message for CRITICAL/WARNING events.

    The LLM output is appended with the original event records so the commander
    can see both the AI analysis and the raw communications.
    """
    bridge = get_bridge_from_config()
    if bridge is None:
        return None

    critical = [e for e in battlefield_events if e.get("level") == "CRITICAL"]
    warnings = [e for e in battlefield_events if e.get("level") == "WARNING"]
    important = critical + warnings

    if not important:
        return None

    event_lines = [
        f"- [{evt.get('level')}][{evt.get('event_type', '?')}] {evt.get('message', '')}"
        for evt in important
    ]
    event_context = "\n".join(event_lines)

    prompt = (
        f"{event_context}\n\n"
        f"🔴×{len(critical)} 🟡×{len(warnings)} — "
        f"用表格列出关键事件（级别/类型/事件/位置），再用一句话给出行动建议。"
    )

    try:
        t0 = time.monotonic()
        result = await bridge.chat(
            system_prompt=ACTIVE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.monotonic() - t0
        logger.info("Proactive LLM call took %.2fs (model=%s)", elapsed, bridge.model)

        return result["text"]
    except Exception as e:
        logger.error("Proactive LLM call failed: %s", e)
        return None


async def _send_proactive_alert(
    session_id: str,
    events: list[dict[str, Any]],
    perception: dict[str, Any],
    show_thinking: bool = False,
) -> None:
    """Generate and send a proactive alert for CRITICAL/WARNING events.

    Tries LLM summarization first; falls back to template if LLM is
    unavailable or the call fails.
    """
    bridge = get_bridge_from_config()

    msg: str | None = None
    summary: str | None = None

    if bridge:
        if show_thinking:
            await active_manager.send_to_session(session_id, {
                "type": "thinking",
                "content": "AI 获取到关键信息，正在分析...",
            })
        msg = await _handle_active_proactive(session_id, events)
        if msg:
            summary = msg[:80].replace("\n", " ").strip("* #")

    if not msg:
        msg = generate_proactive_message(perception)
        if msg:
            summary = generate_proactive_summary(perception)

    if msg and summary:
        active_session_alerts.setdefault(session_id, []).append(msg)
        await active_manager.send_to_session(session_id, {
            "type": "agent_proactive",
            "content": msg,
            "priority": perception["priority"],
            "summary": summary,
        })


# ==================== Situation Compare ====================


SITUATION_COMPARE_PROMPT = """你收到了一份战场态势数据快照，请进行以下分析：

1. **总体态势评估**：基于数据给出当前战场态势等级
2. **关键变化识别**：识别最值得关注的事件和趋势
3. **威胁比对分析**：对比不同级别事件的分布，判断威胁演变方向
4. **行动建议**：给出具体的指挥决策建议

态势数据：
{situation_context}

请按军事通信风格简洁报告，用 🔴🟡🟢 标记威胁级别。"""


async def _handle_fetch_situation(session_id: str, data: dict[str, Any]) -> None:
    """Handle a situation compare request from the frontend."""
    snapshot = data.get("snapshot", {})
    stats = snapshot.get("stats", {})
    recent_events = snapshot.get("recentEvents", [])

    bridge = get_bridge_from_config()
    model_name = bridge.model if bridge else "mock"

    await active_manager.send_to_session(session_id, {
        "type": "thinking",
        "content": f"Overwatch 正在调取态势数据进行比对分析 ({model_name})...",
    })

    await active_manager.send_to_session(session_id, {
        "type": "tool_call",
        "tool": "situation_compare",
        "description": "比对分析态势流式数据",
        "status": "executing",
    })

    session_evts = active_session_events.get(session_id, [])

    event_lines = []
    for evt in (recent_events or session_evts[-10:]):
        lvl = evt.get("level", "INFO")
        msg = evt.get("message", "")
        etype = evt.get("event_type", "?")
        event_lines.append(f"[{lvl}][{etype}] {msg}")

    situation_context = (
        f"事件统计: 🔴 关键 {stats.get('critical', 0)} | "
        f"🟡 警告 {stats.get('warning', 0)} | "
        f"🟢 常规 {stats.get('info', 0)} | "
        f"总计 {stats.get('total', 0)}\n\n"
        f"最近事件:\n" + "\n".join(event_lines)
    )

    await active_manager.send_to_session(session_id, {
        "type": "tool_result",
        "tool": "situation_compare",
        "result": {
            "stats": stats,
            "event_count": len(event_lines),
            "status": "data_captured",
        },
        "status": "completed",
    })

    reply_content: str | None = None

    if bridge:
        try:
            prompt = SITUATION_COMPARE_PROMPT.format(situation_context=situation_context)
            history = session_histories.setdefault(f"active-{session_id}", [])
            history.append({"role": "user", "content": prompt})

            t0 = time.monotonic()
            result = await bridge.chat(
                system_prompt=ACTIVE_SYSTEM_PROMPT,
                messages=history[-20:],
            )
            elapsed = time.monotonic() - t0
            logger.info("Situation compare LLM call took %.2fs (model=%s)", elapsed, bridge.model)

            reply_content = result["text"]
            history.append({"role": "assistant", "content": reply_content})
        except Exception as e:
            logger.error("Situation compare LLM call failed: %s", e)

    if not reply_content:
        reply_content = _generate_mock_situation_compare(stats, recent_events or session_evts[-10:])

    await active_manager.send_to_session(session_id, {
        "type": "agent_reply",
        "content": reply_content,
        "situationSnapshot": snapshot if snapshot else None,
    })


def _generate_mock_situation_compare(
    stats: dict[str, Any],
    events: list[dict[str, Any]],
) -> str:
    """Generate a mock situation comparison report when LLM is unavailable."""
    critical = stats.get("critical", 0)
    warning = stats.get("warning", 0)
    info = stats.get("info", 0)
    total = stats.get("total", 0)

    if critical > 0:
        level = "🔴 **RED — 高度危险**"
        action = "建议立即启动应急响应协议，优先处置关键威胁"
    elif warning > 2:
        level = "🟡 **YELLOW — 态势紧张**"
        action = "建议提升警戒等级，密切关注警告事件演变"
    elif warning > 0:
        level = "🟡 **YELLOW — 需关注**"
        action = "态势可控，建议加强相关区域巡逻"
    else:
        level = "🟢 **GREEN — 态势正常**"
        action = "继续常规监控，无需特殊行动"

    critical_events = [e for e in events if e.get("level") == "CRITICAL"]
    warning_events = [e for e in events if e.get("level") == "WARNING"]
    key_events = critical_events + warning_events

    event_section = ""
    if key_events:
        lines = []
        for evt in key_events[:5]:
            marker = "🔴" if evt.get("level") == "CRITICAL" else "🟡"
            lines.append(f"  {marker} [{evt.get('event_type', '?')}] {evt.get('message', '')}")
        event_section = f"\n**关键事件：**\n" + "\n".join(lines) + "\n"

    return (
        f"📊 **态势比对报告**\n\n"
        f"**当前态势等级：** {level}\n"
        f"**事件分布：** 🔴×{critical} 🟡×{warning} 🟢×{info} （共{total}条）\n"
        f"{event_section}\n"
        f"**趋势判断：** {'威胁持续升级，需要即时干预' if critical > 0 else '态势波动在可控范围'}\n\n"
        f"→ **建议：** {action}"
    )


# ==================== WebSocket Endpoints ====================


@app.websocket("/ws/passive/{session_id}")
async def ws_passive(websocket: WebSocket, session_id: str):
    await passive_manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            message = data.get("message", "")
            if not message:
                continue

            bridge = get_bridge_from_config()
            model_name = bridge.model if bridge else "mock"
            await passive_manager.send_to_session(session_id, {
                "type": "thinking",
                "content": f"正在调用 {model_name} ...",
            })

            events = await _handle_passive(session_id, message)
            for event in events:
                await passive_manager.send_to_session(session_id, event)

    except WebSocketDisconnect:
        await passive_manager.disconnect(session_id, websocket)
        session_histories.pop(f"passive-{session_id}", None)
    except Exception as e:
        logger.error("Passive WS error: %s", e)
        await passive_manager.disconnect(session_id, websocket)
        session_histories.pop(f"passive-{session_id}", None)


@app.websocket("/ws/active/{session_id}")
async def ws_active(websocket: WebSocket, session_id: str):
    await active_manager.connect(session_id, websocket)
    active_session_events.setdefault(session_id, [])

    store = ConfigStore.get()
    mode_label = f"模式: {'LLM (' + store.model + ')' if store.is_llm_mode else 'Mock'}"

    welcome_msg = (
        f"**Overwatch 已上线** · {mode_label}\n\n"
        f"监控已启动，事件将持续推送。直接输入指令即可。"
    )
    # Only send the welcome message on the very first connection for this session
    if session_id not in _welcomed_sessions:
        _welcomed_sessions.add(session_id)
        active_session_alerts.setdefault(session_id, []).append(welcome_msg)
        await active_manager.send_to_session(session_id, {
            "type": "agent_proactive",
            "content": welcome_msg,
            "priority": "INFO",
        })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "start_monitor":
                # Cancel any existing monitor task, then start a fresh loop
                scenario = data.get("scenario")
                _cancel_monitor(session_id)
                task = asyncio.create_task(_run_auto_monitor(session_id, scenario))
                _monitor_tasks[session_id] = task
                logger.info("Auto monitor started via WS: session=%s scenario=%s", session_id, scenario)
                # ACK so the frontend knows the message was received
                await websocket.send_json({"type": "status", "content": "monitor_started"})

            elif msg_type == "stop_monitor":
                _cancel_monitor(session_id)
                await websocket.send_json({"type": "status", "content": "monitor_stopped"})
                logger.info("Auto monitor stopped via WS: session=%s", session_id)

            elif msg_type == "trigger_mock":
                scenario = data.get("scenario")
                events, perception = await trigger_mock_data(active_manager, session_id, scenario)
                active_session_events[session_id].extend(events)
                if perception:
                    await _send_proactive_alert(session_id, events, perception)
                _trim_session_data(session_id)

            elif msg_type == "fetch_situation":
                await _handle_fetch_situation(session_id, data)

            elif msg_type == "message":
                message = data.get("message", "")
                if not message:
                    continue

                summary_ctx = data.get("summaryContext", "")
                if summary_ctx:
                    message = f"{summary_ctx}\n\n**指挥官指令：** {message}"

                bridge = get_bridge_from_config()
                model_name = bridge.model if bridge else "mock"
                await active_manager.send_to_session(session_id, {
                    "type": "thinking",
                    "content": f"Overwatch 分析中 ({model_name})...",
                })

                session_evts = active_session_events.get(session_id, [])
                events = await _handle_active(session_id, message, session_evts)
                for event in events:
                    await active_manager.send_to_session(session_id, event)

    except WebSocketDisconnect:
        await active_manager.disconnect(session_id, websocket)
        logger.info("Active WS disconnected: session=%s", session_id)
    except Exception as e:
        logger.error("Active WS error: %s", e)
        await active_manager.disconnect(session_id, websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
