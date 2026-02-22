"""
Session Manager - 会话管理器

管理 Agent 执行会话的状态和历史记录。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """
    会话状态

    存储会话的运行时状态和历史记录。
    """

    session_id: str
    workspace_id: str
    agent_id: str
    message_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"  # active, paused, completed, error
    executor: Any = field(default=None, repr=False)  # AgentExecutor 引用

    def add_message(self, role: str, content: str | list[dict]) -> None:
        """
        添加消息到历史记录

        Args:
            role: 消息角色 (user, assistant, system)
            content: 消息内容
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.message_history.append(message)
        self.updated_at = datetime.utcnow()

    def get_last_message(self) -> dict[str, Any] | None:
        """获取最后一条消息"""
        if self.message_history:
            return self.message_history[-1]
        return None

    def get_messages_for_api(self) -> list[dict[str, Any]]:
        """
        获取适合 API 调用的消息格式

        Returns:
            消息列表 (不含 timestamp)
        """
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.message_history
        ]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "message_count": len(self.message_history),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class SessionManager:
    """
    会话管理器

    管理会话的创建、查询、更新和删除。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._logger = logging.getLogger(f"{__name__}.SessionManager")

    async def create_session(
        self,
        workspace_id: str,
        agent_id: str,
        metadata: dict[str, Any] | None = None,
        executor: Any = None,
    ) -> SessionState:
        """
        创建会话

        Args:
            workspace_id: 工作区域 ID
            agent_id: Agent ID
            metadata: 元数据 (可选)
            executor: AgentExecutor 实例 (可选)

        Returns:
            SessionState 实例
        """
        session_id = self._generate_session_id()

        session = SessionState(
            session_id=session_id,
            workspace_id=workspace_id,
            agent_id=agent_id,
            metadata=metadata or {},
            executor=executor,
        )

        self._sessions[session_id] = session
        self._logger.info(f"Created session: {session_id} for agent {agent_id}")

        return session

    async def get_session(self, session_id: str) -> SessionState | None:
        """
        获取会话

        Args:
            session_id: 会话 ID

        Returns:
            SessionState 或 None
        """
        return self._sessions.get(session_id)

    async def update_session(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> SessionState | None:
        """
        更新会话

        Args:
            session_id: 会话 ID
            updates: 更新内容

        Returns:
            更新后的 SessionState 或 None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # 更新允许的字段
        allowed_fields = {"status", "metadata"}
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(session, key, value)

        session.updated_at = datetime.utcnow()
        self._logger.debug(f"Updated session: {session_id}")

        return session

    async def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话 ID

        Returns:
            是否成功删除
        """
        session = self._sessions.pop(session_id, None)
        if session:
            # 清理会话关联的资源
            if session.executor:
                try:
                    session.executor.reset()
                except Exception as e:
                    self._logger.warning(f"Failed to reset executor for session {session_id}: {e}")

            self._logger.info(f"Deleted session: {session_id}")
            return True
        return False

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str | list[dict],
    ) -> bool:
        """
        添加消息到会话

        Args:
            session_id: 会话 ID
            role: 消息角色
            content: 消息内容

        Returns:
            是否成功添加
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.add_message(role, content)
        self._logger.debug(f"Added {role} message to session: {session_id}")

        return True

    def list_sessions(
        self,
        workspace_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[SessionState]:
        """
        列出会话

        Args:
            workspace_id: 过滤工作区域 ID (可选)
            agent_id: 过滤 Agent ID (可选)
            status: 过滤状态 (可选)

        Returns:
            SessionState 列表
        """
        sessions = list(self._sessions.values())

        if workspace_id:
            sessions = [s for s in sessions if s.workspace_id == workspace_id]

        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]

        if status:
            sessions = [s for s in sessions if s.status == status]

        # 按创建时间倒序排列
        sessions.sort(key=lambda s: s.created_at, reverse=True)

        return sessions

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        status_counts: dict[str, int] = {}
        for session in self._sessions.values():
            status_counts[session.status] = status_counts.get(session.status, 0) + 1

        return {
            "total_sessions": len(self._sessions),
            "by_status": status_counts,
        }

    def clear(self) -> None:
        """清空所有会话"""
        # 重置所有执行器
        for session in self._sessions.values():
            if session.executor:
                try:
                    session.executor.reset()
                except Exception as e:
                    self._logger.warning(f"Failed to reset executor: {e}")

        self._sessions.clear()
        self._logger.info("Cleared all sessions")

    def _generate_session_id(self) -> str:
        """生成会话 ID"""
        return f"sess-{uuid.uuid4().hex[:12]}"
