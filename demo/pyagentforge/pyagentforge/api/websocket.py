"""
WebSocket 路由

实现流式通信
"""

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from pyagentforge.config.settings import get_settings
from pyagentforge.core.engine import AgentEngine
from pyagentforge.providers.anthropic_provider import AnthropicProvider
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.engines: dict[str, AgentEngine] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """接受连接"""
        await websocket.accept()
        self.active_connections[session_id] = websocket

        # 创建引擎
        settings = get_settings()
        provider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.default_model,
        )
        tools = ToolRegistry()
        tools.register_builtin_tools()

        self.engines[session_id] = AgentEngine(
            provider=provider,
            tool_registry=tools,
        )

        logger.info(
            "WebSocket connected",
            extra_data={"session_id": session_id},
        )

    def disconnect(self, session_id: str) -> None:
        """断开连接"""
        self.active_connections.pop(session_id, None)
        self.engines.pop(session_id, None)

        logger.info(
            "WebSocket disconnected",
            extra_data={"session_id": session_id},
        )

    async def send_json(self, session_id: str, data: dict[str, Any]) -> None:
        """发送 JSON 消息"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(data)


manager = ConnectionManager()


@router.websocket("/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket 端点"""
    await manager.connect(websocket, session_id)

    try:
        while True:
            # 接收消息
            data = await websocket.receive_json()

            message = data.get("message", "")
            if not message:
                continue

            logger.debug(
                "WebSocket received message",
                extra_data={"session_id": session_id, "message_length": len(message)},
            )

            engine = manager.engines.get(session_id)
            if not engine:
                await manager.send_json(
                    session_id,
                    {"type": "error", "message": "Session not found"},
                )
                continue

            # 发送开始事件
            await manager.send_json(
                session_id,
                {"type": "start", "session_id": session_id},
            )

            try:
                # 流式运行 Agent
                async for event in engine.run_stream(message):
                    if isinstance(event, dict):
                        await manager.send_json(session_id, event)

            except Exception as e:
                logger.error(
                    "WebSocket processing error",
                    extra_data={"session_id": session_id, "error": str(e)},
                )
                await manager.send_json(
                    session_id,
                    {"type": "error", "message": str(e)},
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(
            "WebSocket error",
            extra_data={"session_id": session_id, "error": str(e)},
        )
        manager.disconnect(session_id)
