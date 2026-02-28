"""
Agent Demo Backend Server

FastAPI application providing WebSocket-based chat for passive and active agents.
LLM calls are driven by pyagentforge AgentEngine, which handles the full
tool-calling loop, context management, and streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from active_handler import (
    AVAILABLE_SCENARIOS,
    get_tool_list as active_tools,
    trigger_mock_data,
)
from config_store import ConfigStore
from engine_manager import ACTIVE_SYSTEM_PROMPT, EngineManager
from llm_provider import get_provider_from_config
from passive_handler import get_tool_list as passive_tools
from ws_manager import ConnectionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="NeuroForge Agent Demo", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

passive_manager = ConnectionManager()
active_manager = ConnectionManager()

# Active agent per-session state (still needed for monitor loop + frontend display)
active_session_events: dict[str, list[dict[str, Any]]] = {}
active_session_alerts: dict[str, list[str]] = {}
# Per-session agent config overrides (set via WS "set_agent_config" or REST)
active_session_agent_config: dict[str, dict[str, Any]] = {}

MAX_SESSION_EVENTS = 200
MAX_SESSION_ALERTS = 50

# Per-session auto-monitor tasks
_monitor_tasks: dict[str, asyncio.Task] = {}
MONITOR_INTERVAL_SECONDS = 15

# Sessions that have already received the welcome message (survives reconnects)
_welcomed_sessions: set[str] = set()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class TriggerMockRequest(BaseModel):
    session_id: str
    scenario: str | None = None


class AgentConfigRequest(BaseModel):
    """运行时 Agent 配置覆盖（优先级高于 agent.yaml 默认值）"""

    session_id: str
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    max_iterations: int | None = None
    system_prompt: str | None = None
    extra: dict[str, Any] | None = None


class ConfigUpdateRequest(BaseModel):
    mode: str | None = None
    provider: str | None = None
    api_type: str | None = None
    auth_header_type: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cleanup_active_session(session_id: str) -> None:
    """Remove in-memory state for an active session."""
    active_session_events.pop(session_id, None)
    active_session_alerts.pop(session_id, None)
    active_session_agent_config.pop(session_id, None)
    EngineManager.destroy_active(session_id)


def _trim_session_data(session_id: str) -> None:
    evts = active_session_events.get(session_id)
    if evts and len(evts) > MAX_SESSION_EVENTS:
        active_session_events[session_id] = evts[-MAX_SESSION_EVENTS:]
    alerts = active_session_alerts.get(session_id)
    if alerts and len(alerts) > MAX_SESSION_ALERTS:
        active_session_alerts[session_id] = alerts[-MAX_SESSION_ALERTS:]


def _cancel_monitor(session_id: str) -> None:
    task = _monitor_tasks.pop(session_id, None)
    if task and not task.done():
        task.cancel()


MONITOR_DISCONNECT_TIMEOUT_S = 60


async def _run_auto_monitor(session_id: str, scenario: str | None) -> None:
    """Continuously push mock battlefield data at a fixed interval."""
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
        current_task = asyncio.current_task()
        if _monitor_tasks.get(session_id) is current_task:
            _monitor_tasks.pop(session_id, None)
        if not active_manager.has_connections(session_id):
            _cleanup_active_session(session_id)


# ---------------------------------------------------------------------------
# Stream helpers
# ---------------------------------------------------------------------------


def _extract_delta(raw_event: Any) -> str:
    """Extract text delta from a provider stream event (OpenAI or Anthropic format)."""
    if isinstance(raw_event, dict):
        if raw_event.get("type") == "text_delta":
            return raw_event.get("text", "")
        return ""
    # Anthropic SDK: ContentBlockDeltaEvent
    if hasattr(raw_event, "type") and getattr(raw_event, "type", None) == "content_block_delta":
        delta = getattr(raw_event, "delta", None)
        if delta:
            return getattr(delta, "text", "") or ""
    return ""


def _map_engine_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Map an AgentEngine stream event to a WebSocket message dict (or None to skip)."""
    etype = event.get("type")

    if etype == "phase_start":
        label = event.get("phase_label", "")
        return {"type": "thinking", "content": f"[{label}] 正在处理..."}

    if etype == "stream":
        delta = _extract_delta(event.get("event"))
        if delta:
            return {"type": "stream_delta", "content": delta}
        return None

    if etype == "tool_start":
        tool_name = event.get("tool_name", "")
        return {
            "type": "tool_call",
            "tool": tool_name,
            "description": f"执行 {tool_name}...",
            "status": "executing",
        }

    if etype == "tool_result":
        result_str = str(event.get("result", ""))
        if len(result_str) > 500:
            result_str = result_str[:500] + "...(截断)"
        return {
            "type": "tool_result",
            "tool": event.get("tool_id", ""),
            "result": {"output": result_str},
            "status": "completed",
        }

    if etype == "error":
        return {"type": "agent_reply", "content": f"⚠️ {event.get('message', '未知错误')}"}

    return None


async def _stream_to_ws(
    engine: Any,
    message: str,
    session_id: str,
    manager: ConnectionManager,
    extra_reply_fields: dict[str, Any] | None = None,
) -> str:
    """
    Drive engine.run_stream() and forward each event to the WebSocket.
    Returns the final reply text.
    """
    full_text = ""
    async for event in engine.run_stream(message):
        etype = event.get("type")
        if etype == "complete":
            text = event.get("text", "")
            full_text = text
            reply: dict[str, Any] = {"type": "agent_reply", "content": text}
            if extra_reply_fields:
                reply.update(extra_reply_fields)
            await manager.send_to_session(session_id, reply)
        else:
            ws_msg = _map_engine_event(event)
            if ws_msg:
                await manager.send_to_session(session_id, ws_msg)
    return full_text


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


@app.get("/api/config")
async def get_config():
    store = ConfigStore.get()
    return store.get_safe_config()


@app.put("/api/config")
async def update_config(req: ConfigUpdateRequest):
    store = ConfigStore.get()
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = store.update(updates)
    # Invalidate all cached engines so next call uses the new config
    EngineManager.reset_all()
    logger.info("Config updated — all engines reset")
    return result


class TestConnectionRequest(BaseModel):
    provider: str | None = None
    api_type: str | None = None
    auth_header_type: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


@app.post("/api/config/test")
async def test_connection(req: TestConnectionRequest | None = None):
    """Test LLM connection using a minimal one-shot call."""
    from llm_provider import create_provider

    store = ConfigStore.get()
    provider_name = (req and req.provider) or store.provider
    api_type = (req and req.api_type) or store.api_type
    api_key = ((req and req.api_key) or store.api_key or "").strip()
    model = (req and req.model) or store.model
    base_url = (req and req.base_url) or store.base_url

    if not api_key:
        return {"success": False, "error": "API Key 未配置"}

    provider = create_provider(
        provider_name=provider_name,
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=0.3,
        max_tokens=256,
        api_type=api_type,
    )
    if provider is None:
        return {"success": False, "error": f"不支持的 provider: {provider_name}"}

    try:
        response = await asyncio.wait_for(
            provider.create_message(
                system="Reply with exactly: CONNECTION_OK",
                messages=[{"role": "user", "content": "ping"}],
                tools=[],
                max_tokens=256,
            ),
            timeout=30.0,
        )
        return {"success": True, "response": response.text[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/config/models")
async def list_models(provider: str = "anthropic"):
    return {"models": ConfigStore.get_models_for_provider(provider)}


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    store = ConfigStore.get()
    return {
        "status": "ok",
        "service": "agent-demo",
        "model": store.model,
    }


@app.post("/api/chat/passive")
async def chat_passive(req: ChatRequest):
    """REST (non-streaming) passive chat — uses engine.run()."""
    sid = req.session_id or str(uuid.uuid4())
    provider = get_provider_from_config()
    engine = EngineManager.get_or_create_passive(sid, provider)
    t0 = time.monotonic()
    try:
        result = await engine.run(req.message)
        elapsed = time.monotonic() - t0
        logger.info("REST passive engine run %.2fs model=%s", elapsed, provider.model)
        return {
            "events": [
                {
                    "type": "tool_result",
                    "tool": "llm_call",
                    "result": {"model": provider.model, "elapsed_s": round(elapsed, 2)},
                    "status": "completed",
                },
                {"type": "agent_reply", "content": result},
            ],
            "session_id": sid,
        }
    except Exception as e:
        return {
            "events": [{"type": "agent_reply", "content": f"LLM 调用失败: {e}"}],
            "session_id": sid,
        }


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


@app.put("/api/active/agent-config")
async def set_active_agent_config(req: AgentConfigRequest):
    """
    设置指定 session 的 active-agent 运行时配置覆盖。

    调用后，该 session 下次创建引擎时将使用新配置；
    已缓存的引擎会因 fingerprint 变化而自动重建。
    """
    overrides: dict[str, Any] = {
        k: v
        for k, v in req.model_dump(exclude={"session_id"}).items()
        if v is not None
    }
    if overrides:
        active_session_agent_config[req.session_id] = overrides
        # 销毁旧引擎，下次调用时按新配置重建
        EngineManager.destroy_active(req.session_id)
        logger.info(
            "Agent config updated for session=%s: %s", req.session_id, list(overrides.keys())
        )
    else:
        active_session_agent_config.pop(req.session_id, None)
        EngineManager.destroy_active(req.session_id)
        logger.info("Agent config cleared for session=%s", req.session_id)

    return {
        "session_id": req.session_id,
        "agent_config": active_session_agent_config.get(req.session_id, {}),
    }


@app.get("/api/active/agent-config/{session_id}")
async def get_active_agent_config(session_id: str):
    """获取指定 session 当前的 active-agent 运行时配置覆盖。"""
    return {
        "session_id": session_id,
        "agent_config": active_session_agent_config.get(session_id, {}),
    }


# ---------------------------------------------------------------------------
# LLM chat logic (engine-driven)
# ---------------------------------------------------------------------------


async def _stream_passive_to_ws(session_id: str, message: str) -> None:
    """Stream passive agent response to WebSocket via AgentEngine."""
    provider = get_provider_from_config()
    engine = EngineManager.get_or_create_passive(session_id, provider)
    try:
        t0 = time.monotonic()
        await _stream_to_ws(engine, message, session_id, passive_manager)
        logger.info("Passive stream %.2fs session=%s model=%s", time.monotonic() - t0, session_id, provider.model)
    except Exception as e:
        logger.error("Passive stream error session=%s: %s", session_id, e)
        await passive_manager.send_to_session(session_id, {
            "type": "agent_reply",
            "content": f"LLM 调用失败: {e}",
        })


async def _stream_active_to_ws(session_id: str, message: str) -> None:
    """Stream active agent response to WebSocket via AgentEngine."""
    provider = get_provider_from_config()

    # Inject battlefield context into the user message
    session_evts = active_session_events.get(session_id, [])
    context_parts = [
        f"[{evt.get('level', '?')}] {evt.get('message', '')}"
        for evt in session_evts[-8:]
    ]
    user_msg = message
    if context_parts:
        user_msg = f"战场数据:\n" + "\n".join(context_parts) + f"\n\n指令: {message}"

    agent_cfg = active_session_agent_config.get(session_id)
    engine = EngineManager.get_or_create_active(session_id, provider, config_overrides=agent_cfg)
    try:
        t0 = time.monotonic()
        await _stream_to_ws(engine, user_msg, session_id, active_manager)
        logger.info("Active stream %.2fs session=%s model=%s", time.monotonic() - t0, session_id, provider.model)
    except Exception as e:
        logger.error("Active stream error session=%s: %s", session_id, e)
        await active_manager.send_to_session(session_id, {
            "type": "agent_reply",
            "content": f"LLM 调用失败: {e}",
        })


async def _handle_active_proactive(session_id: str, battlefield_events: list[dict]) -> str | None:
    """
    One-shot LLM call to summarize CRITICAL/WARNING events for a proactive alert.
    Uses the provider directly (no session history) to keep alerts independent.
    """
    provider = get_provider_from_config()
    if provider is None:
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
    prompt = (
        "\n".join(event_lines) + "\n\n"
        f"🔴×{len(critical)} 🟡×{len(warnings)} — "
        "用表格列出关键事件（级别/类型/事件/位置），再用一句话给出行动建议。"
    )

    try:
        t0 = time.monotonic()
        response = await asyncio.wait_for(
            provider.create_message(
                system=ACTIVE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                tools=[],
                max_tokens=1024,
            ),
            timeout=60.0,
        )
        logger.info("Proactive LLM %.2fs model=%s", time.monotonic() - t0, provider.model)
        return response.text
    except Exception as e:
        logger.error("Proactive LLM call failed: %s", e)
        return None


async def _send_proactive_alert(
    session_id: str,
    events: list[dict[str, Any]],
    perception: dict[str, Any],
    show_thinking: bool = False,
) -> None:
    """Generate and push a proactive alert for CRITICAL/WARNING events."""
    provider = get_provider_from_config()

    if show_thinking:
        await active_manager.send_to_session(session_id, {
            "type": "thinking",
            "content": "AI 获取到关键信息，正在分析...",
        })

    msg = await _handle_active_proactive(session_id, events)
    if not msg:
        return

    summary = msg[:80].replace("\n", " ").strip("* #")
    active_session_alerts.setdefault(session_id, []).append(msg)
    await active_manager.send_to_session(session_id, {
        "type": "agent_proactive",
        "content": msg,
        "priority": perception["priority"],
        "summary": summary,
    })


# ---------------------------------------------------------------------------
# Situation compare (engine-driven)
# ---------------------------------------------------------------------------


async def _handle_fetch_situation(session_id: str, data: dict[str, Any]) -> None:
    """Handle a situation compare request using the active AgentEngine."""
    snapshot = data.get("snapshot", {})
    stats = snapshot.get("stats", {})
    recent_events = snapshot.get("recentEvents", [])

    provider = get_provider_from_config()

    await active_manager.send_to_session(session_id, {
        "type": "thinking",
        "content": f"Overwatch 正在调取态势数据进行比对分析 ({ConfigStore.get().model})...",
    })

    # Build structured prompt with the situation data embedded
    session_evts = active_session_events.get(session_id, [])
    events_for_analysis = recent_events or session_evts[-10:]

    stats_json = json.dumps(stats, ensure_ascii=False)
    events_json = json.dumps(events_for_analysis[:10], ensure_ascii=False)

    user_message = (
        "请使用 situation_compare 工具分析以下态势数据，然后生成完整战场评估报告：\n\n"
        f"统计数据：{stats_json}\n\n"
        f"最近事件：{events_json}"
    )

    agent_cfg = active_session_agent_config.get(session_id)
    engine = EngineManager.get_or_create_active(session_id, provider, config_overrides=agent_cfg)
    try:
        await _stream_to_ws(
            engine,
            user_message,
            session_id,
            active_manager,
            extra_reply_fields={"situationSnapshot": snapshot if snapshot else None},
        )
    except Exception as e:
        logger.error("Situation compare failed session=%s: %s", session_id, e)
        await active_manager.send_to_session(session_id, {
            "type": "agent_reply",
            "content": f"⚠️ 态势分析失败: {e}",
            "situationSnapshot": snapshot if snapshot else None,
        })


# ---------------------------------------------------------------------------
# WebSocket endpoints
# ---------------------------------------------------------------------------


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

            await passive_manager.send_to_session(session_id, {
                "type": "thinking",
                "content": f"正在调用 {ConfigStore.get().model} ...",
            })

            await _stream_passive_to_ws(session_id, message)

    except WebSocketDisconnect:
        await passive_manager.disconnect(session_id, websocket)
        EngineManager.destroy_passive(session_id)
    except Exception as e:
        logger.error("Passive WS error: %s", e)
        await passive_manager.disconnect(session_id, websocket)
        EngineManager.destroy_passive(session_id)


@app.websocket("/ws/active/{session_id}")
async def ws_active(websocket: WebSocket, session_id: str):
    await active_manager.connect(session_id, websocket)
    active_session_events.setdefault(session_id, [])

    welcome_msg = (
        f"**Overwatch 已上线** · 模型: {ConfigStore.get().model}\n\n"
        f"监控已启动，事件将持续推送。直接输入指令即可。"
    )
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

            if msg_type == "set_agent_config":
                # 上游通过 WS 动态更新本 session 的 agent 配置
                overrides: dict[str, Any] = {
                    k: v
                    for k, v in data.items()
                    if k not in {"type"} and v is not None
                }
                if overrides:
                    active_session_agent_config[session_id] = overrides
                    EngineManager.destroy_active(session_id)
                    logger.info(
                        "WS agent config set session=%s keys=%s", session_id, list(overrides.keys())
                    )
                else:
                    active_session_agent_config.pop(session_id, None)
                    EngineManager.destroy_active(session_id)
                await websocket.send_json({
                    "type": "status",
                    "content": "agent_config_updated",
                    "agent_config": active_session_agent_config.get(session_id, {}),
                })

            elif msg_type == "start_monitor":
                scenario = data.get("scenario")
                _cancel_monitor(session_id)
                task = asyncio.create_task(_run_auto_monitor(session_id, scenario))
                _monitor_tasks[session_id] = task
                logger.info("Auto monitor started via WS: session=%s scenario=%s", session_id, scenario)
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

                await active_manager.send_to_session(session_id, {
                    "type": "thinking",
                    "content": f"Overwatch 分析中 ({ConfigStore.get().model})...",
                })

                await _stream_active_to_ws(session_id, message)

    except WebSocketDisconnect:
        await active_manager.disconnect(session_id, websocket)
        logger.info("Active WS disconnected: session=%s", session_id)
    except Exception as e:
        logger.error("Active WS error: %s", e)
        await active_manager.disconnect(session_id, websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
