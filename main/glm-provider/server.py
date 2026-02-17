"""
GLM Provider Backend Server

使用 GLM 模型的 PyAgentForge 后端服务
支持 HTTP REST API 和 WebSocket 流式通信
"""

import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pyagentforge"))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 导入 PyAgentForge 组件
from pyagentforge.agents.config import AgentConfig
from pyagentforge.core.engine import AgentEngine
from pyagentforge.tools.registry import ToolRegistry

# 导入 GLM Provider
from glm_provider import GLMProvider

# ============ 配置 ============

GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4-flash")
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8100"))


# ============ 请求/响应模型 ============

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    agent_id: str | None = Field(default=None, description="Agent ID")
    system_prompt: str | None = Field(default=None, description="系统提示词")
    model: str | None = Field(default=None, description="模型名称")


class CreateSessionResponse(BaseModel):
    """创建会话响应"""
    session_id: str
    status: str


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    message: str = Field(..., description="用户消息")
    stream: bool = Field(default=False, description="是否流式响应")


class MessageResponse(BaseModel):
    """消息响应"""
    role: str
    content: str


class SessionDetail(BaseModel):
    """会话详情"""
    session_id: str
    status: str
    message_count: int
    messages: list[dict[str, Any]]


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    provider: str


# ============ 会话存储 ============

_sessions: dict[str, AgentEngine] = {}


def get_or_create_engine(
    session_id: str | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
) -> AgentEngine:
    """获取或创建引擎"""
    if session_id and session_id in _sessions:
        return _sessions[session_id]

    # 创建 GLM Provider
    actual_model = model or GLM_MODEL
    provider = GLMProvider(
        api_key=GLM_API_KEY,
        model=actual_model,
    )

    # 创建工具注册表
    tools = ToolRegistry()
    tools.register_builtin_tools()

    # 创建配置
    config = AgentConfig(system_prompt=system_prompt or "你是一个有帮助的 AI 助手。")

    # 创建引擎
    engine = AgentEngine(
        provider=provider,
        tool_registry=tools,
        config=config,
    )

    _sessions[engine.session_id] = engine
    print(f"[Server] Created session: {engine.session_id}")
    return engine


# ============ WebSocket 管理器 ============

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
        provider = GLMProvider(
            api_key=GLM_API_KEY,
            model=GLM_MODEL,
        )
        tools = ToolRegistry()
        tools.register_builtin_tools()

        self.engines[session_id] = AgentEngine(
            provider=provider,
            tool_registry=tools,
        )
        print(f"[WebSocket] Connected: {session_id}")

    def disconnect(self, session_id: str) -> None:
        """断开连接"""
        self.active_connections.pop(session_id, None)
        self.engines.pop(session_id, None)
        print(f"[WebSocket] Disconnected: {session_id}")

    async def send_json(self, session_id: str, data: dict[str, Any]) -> None:
        """发送 JSON 消息"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(data)


manager = ConnectionManager()


# ============ 应用生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    print(f"[Server] GLM Provider Backend starting...")
    print(f"[Server] Model: {GLM_MODEL}")
    print(f"[Server] Host: {SERVER_HOST}:{SERVER_PORT}")

    if not GLM_API_KEY:
        print("[Warning] GLM_API_KEY not set! Please set the environment variable.")

    yield

    print("[Server] Shutting down...")


# ============ 创建应用 ============

app = FastAPI(
    title="PyAgentForge GLM Backend",
    description="使用 GLM 模型的 PyAgentForge 测试后端",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ API 端点 ============

@app.get("/")
async def root() -> dict:
    """根路径"""
    return {
        "name": "PyAgentForge GLM Backend",
        "version": "1.0.0",
        "model": GLM_MODEL,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check() -> dict:
    """健康检查"""
    return {"status": "healthy", "provider": "glm", "model": GLM_MODEL}


@app.get("/api/models", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    """列出可用模型"""
    return [
        ModelInfo(id="glm-5", name="GLM-5", provider="glm"),
        ModelInfo(id="glm-4-flash", name="GLM-4-Flash", provider="glm"),
        ModelInfo(id="glm-4-plus", name="GLM-4-Plus", provider="glm"),
        ModelInfo(id="glm-4-air", name="GLM-4-Air", provider="glm"),
        ModelInfo(id="glm-4-long", name="GLM-4-Long", provider="glm"),
    ]


@app.post("/api/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
    """创建新会话"""
    engine = get_or_create_engine(
        system_prompt=request.system_prompt,
        model=request.model,
    )
    return CreateSessionResponse(
        session_id=engine.session_id,
        status="created",
    )


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """获取会话详情"""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    engine = _sessions[session_id]
    return SessionDetail(
        session_id=session_id,
        status="active",
        message_count=len(engine.context),
        messages=engine.context.get_messages_for_api(),
    )


@app.post("/api/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(session_id: str, request: SendMessageRequest) -> MessageResponse:
    """发送消息给 Agent"""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    engine = _sessions[session_id]
    print(f"[Server] Processing message for session {session_id}: {request.message[:50]}...")

    try:
        response = await engine.run(request.message)
        return MessageResponse(role="assistant", content=response)
    except Exception as e:
        print(f"[Server] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """删除会话"""
    if session_id in _sessions:
        del _sessions[session_id]
        print(f"[Server] Deleted session: {session_id}")
    return {"status": "deleted"}


@app.get("/api/sessions")
async def list_sessions() -> dict[str, list[str]]:
    """列出所有会话"""
    return {"sessions": list(_sessions.keys())}


# ============ WebSocket 端点 ============

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """WebSocket 端点"""
    await manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            if not message:
                continue

            print(f"[WebSocket] Received: {message[:50]}...")

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
                print(f"[WebSocket] Error: {e}")
                await manager.send_json(
                    session_id,
                    {"type": "error", "message": str(e)},
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        manager.disconnect(session_id)


# ============ 启动入口 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
    )
