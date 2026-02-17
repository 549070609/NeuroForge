"""
会话 API 路由

管理会话的创建、查询和消息发送
使用 JSONL 文件持久化会话消息
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from pyagentforge.config.settings import get_settings
from pyagentforge.core.context import ContextManager
from pyagentforge.core.engine import AgentEngine
from pyagentforge.core.persistence import SessionManager, SessionPersistence
from pyagentforge.providers.anthropic_provider import AnthropicProvider
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============ 请求/响应模型 ============


class CreateSessionRequest(BaseModel):
    """创建会话请求"""

    agent_id: str | None = Field(default=None, description="Agent ID")
    system_prompt: str | None = Field(default=None, description="系统提示词")


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


# ============ 会话存储 (JSONL 持久化) ============

# 使用 SessionManager 管理 JSONL 文件存储
_session_manager = SessionManager(sessions_dir=".sessions")

# 内存中缓存 AgentEngine 实例
_engines: dict[str, AgentEngine] = {}

# 持久化实例缓存
_persistences: dict[str, SessionPersistence] = {}


def get_or_create_engine(session_id: str | None = None) -> AgentEngine:
    """获取或创建引擎，支持从 JSONL 恢复"""
    settings = get_settings()

    # 如果提供了 session_id，尝试加载现有会话
    if session_id:
        # 检查内存缓存
        if session_id in _engines:
            return _engines[session_id]

        # 尝试从 JSONL 加载
        persistence = _session_manager.load_session(session_id)
        if persistence:
            _persistences[session_id] = persistence

            # 从 JSONL 恢复消息历史
            context = ContextManager()
            for msg in persistence.read_messages():
                context.messages.append(msg)  # 直接添加原始消息

            # 创建引擎并恢复上下文
            provider = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.default_model,
            )
            tools = ToolRegistry()
            tools.register_builtin_tools()

            engine = AgentEngine(
                provider=provider,
                tool_registry=tools,
                context=context,
            )
            # 使用持久化的 session_id
            engine._session_id = session_id

            _engines[session_id] = engine
            logger.info(
                "Loaded session from JSONL",
                extra_data={"session_id": session_id, "message_count": len(context)},
            )
            return engine

    # 创建新会话
    new_session_id = f"session_{uuid.uuid4().hex[:12]}"

    provider = AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model=settings.default_model,
    )

    tools = ToolRegistry()
    tools.register_builtin_tools()

    engine = AgentEngine(provider=provider, tool_registry=tools)
    # 使用统一的 session_id
    engine._session_id = new_session_id

    # 创建持久化存储
    persistence = _session_manager.create_session(
        model=settings.default_model,
        title=f"Session {new_session_id[:12]}",
    )
    # 使用持久化生成的 session_id
    engine._session_id = persistence.session_id

    _engines[engine.session_id] = engine
    _persistences[engine.session_id] = persistence

    logger.info(
        "Created new session with JSONL storage",
        extra_data={"session_id": engine.session_id},
    )

    return engine


# ============ API 端点 ============


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
    """创建新会话"""
    engine = get_or_create_engine()

    logger.info(
        "Created session",
        extra_data={"session_id": engine.session_id},
    )

    return CreateSessionResponse(
        session_id=engine.session_id,
        status="created",
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """获取会话详情"""
    engine = get_or_create_engine(session_id)

    return SessionDetail(
        session_id=session_id,
        status="active",
        message_count=len(engine.context),
        messages=engine.context.get_messages_for_api(),
    )


@router.post("/{session_id}/messages", response_model=MessageResponse)
async def send_message(session_id: str, request: SendMessageRequest) -> MessageResponse:
    """发送消息给 Agent"""
    engine = get_or_create_engine(session_id)
    persistence = _persistences.get(session_id)

    logger.info(
        "Received message",
        extra_data={"session_id": session_id, "message_length": len(request.message)},
    )

    try:
        # 持久化用户消息
        if persistence:
            user_msg = {"role": "user", "content": request.message}
            persistence.append_message(user_msg)

        response = await engine.run(request.message)

        # 持久化助手响应
        if persistence:
            assistant_msg = {"role": "assistant", "content": response}
            persistence.append_message(assistant_msg)

        return MessageResponse(
            role="assistant",
            content=response,
        )
    except Exception as e:
        logger.error(
            "Error processing message",
            extra_data={"session_id": session_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str) -> None:
    """删除会话（同时删除 JSONL 文件）"""
    # 删除内存中的引擎
    if session_id in _engines:
        del _engines[session_id]

    # 删除持久化缓存
    if session_id in _persistences:
        del _persistences[session_id]

    # 删除 JSONL 文件
    persistence = _session_manager.load_session(session_id)
    if persistence:
        persistence.delete_session()

    logger.info(
        "Deleted session",
        extra_data={"session_id": session_id},
    )


@router.get("")
async def list_sessions() -> dict[str, list[dict[str, Any]]]:
    """列出所有会话（从 JSONL 存储）"""
    sessions = _session_manager.list_sessions()
    return {"sessions": sessions}
