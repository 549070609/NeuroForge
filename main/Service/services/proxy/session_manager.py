"""Session manager with persistent state backend."""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ...persistence import StateStore

logger = logging.getLogger(__name__)


def _parse_datetime(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


@dataclass
class SessionState:
    """Session runtime state."""

    session_id: str
    workspace_id: str
    agent_id: str
    message_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "active"  # active, paused, completed, error
    version: int = 0
    trace_id: str | None = None
    executor: Any = field(default=None, repr=False)  # in-process only

    def add_message(self, role: str, content: str | list[dict]) -> None:
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.message_history.append(message)
        self.updated_at = datetime.utcnow()

    def get_last_message(self) -> dict[str, Any] | None:
        if self.message_history:
            return self.message_history[-1]
        return None

    def get_messages_for_api(self) -> list[dict[str, Any]]:
        return [{"role": msg["role"], "content": msg["content"]} for msg in self.message_history]

    def to_store_value(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "message_history": copy.deepcopy(self.message_history),
            "metadata": copy.deepcopy(self.metadata),
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "message_count": len(self.message_history),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_store_value(cls, value: dict[str, Any], version: int, executor: Any = None) -> SessionState:
        return cls(
            session_id=str(value.get("session_id", "")),
            workspace_id=str(value.get("workspace_id", "")),
            agent_id=str(value.get("agent_id", "")),
            message_history=list(value.get("message_history", [])),
            metadata=dict(value.get("metadata", {})),
            created_at=_parse_datetime(value.get("created_at")),
            updated_at=_parse_datetime(value.get("updated_at")),
            status=str(value.get("status", "active")),
            version=version,
            trace_id=value.get("trace_id"),
            executor=executor,
        )


class SessionManager:
    """Persistent session manager with optimistic concurrency."""

    SESSION_NAMESPACE = "session"

    def __init__(
        self,
        store: StateStore,
        *,
        session_ttl: int = 3600,
        max_sessions: int = 100,
    ) -> None:
        self._store = store
        self._session_ttl = session_ttl
        self._max_sessions = max_sessions
        self._executors: dict[str, Any] = {}
        self._logger = logging.getLogger(f"{__name__}.SessionManager")

    async def create_session(
        self,
        workspace_id: str,
        agent_id: str,
        metadata: dict[str, Any] | None = None,
        executor: Any = None,
        idempotency_key: str | None = None,
    ) -> SessionState:
        existing_sessions = await self.list_sessions()
        if self._max_sessions > 0 and len(existing_sessions) >= self._max_sessions:
            raise ValueError(f"Maximum session limit reached: {self._max_sessions}")

        for _ in range(5):
            session_id = self._generate_session_id()
            session = SessionState(
                session_id=session_id,
                workspace_id=workspace_id,
                agent_id=agent_id,
                metadata=metadata or {},
                executor=executor,
            )
            write_result = await self._store.set(
                session_id,
                session.to_store_value(),
                namespace=self.SESSION_NAMESPACE,
                ttl=self._session_ttl,
                expected_version=0,
                idempotency_key=idempotency_key,
            )
            if write_result.applied and write_result.record:
                session.version = write_result.record.version
                if executor is not None:
                    self._executors[session_id] = executor
                self._logger.info("Created session: %s for agent %s", session_id, agent_id)
                return session

        raise RuntimeError("Failed to create session after multiple retries")

    async def get_session(self, session_id: str) -> SessionState | None:
        record = await self._store.get(session_id, namespace=self.SESSION_NAMESPACE)
        if record is None:
            self._executors.pop(session_id, None)
            return None
        return SessionState.from_store_value(
            value=record.value,
            version=record.version,
            executor=self._executors.get(session_id),
        )

    async def update_session(self, session_id: str, updates: dict[str, Any]) -> SessionState | None:
        session = await self.get_session(session_id)
        if not session:
            return None

        allowed_fields = {"status", "metadata", "trace_id"}
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(session, key, value)
        session.updated_at = datetime.utcnow()

        write_result = await self._store.set(
            session_id,
            session.to_store_value(),
            namespace=self.SESSION_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=session.version,
        )
        if not write_result.applied or write_result.record is None:
            self._logger.warning("Session update conflict: %s", session_id)
            return None

        session.version = write_result.record.version
        return session

    async def delete_session(self, session_id: str) -> bool:
        session = await self.get_session(session_id)
        if not session:
            self._executors.pop(session_id, None)
            return False

        executor = self._executors.pop(session_id, None)
        if executor:
            try:
                executor.reset()
            except Exception as exc:
                self._logger.warning("Failed to reset executor for session %s: %s", session_id, exc)

        deleted = await self._store.delete(
            session_id,
            namespace=self.SESSION_NAMESPACE,
            expected_version=session.version,
        )
        if deleted:
            self._logger.info("Deleted session: %s", session_id)
        return deleted

    async def add_message(self, session_id: str, role: str, content: str | list[dict]) -> bool:
        session = await self.get_session(session_id)
        if not session:
            return False

        session.add_message(role, content)
        write_result = await self._store.set(
            session_id,
            session.to_store_value(),
            namespace=self.SESSION_NAMESPACE,
            ttl=self._session_ttl,
            expected_version=session.version,
        )
        if not write_result.applied or write_result.record is None:
            self._logger.warning("Session message append conflict: %s", session_id)
            return False
        session.version = write_result.record.version
        return True

    async def list_sessions(
        self,
        workspace_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
    ) -> list[SessionState]:
        records = await self._store.list(namespace=self.SESSION_NAMESPACE)
        sessions = [
            SessionState.from_store_value(
                value=record.value,
                version=record.version,
                executor=self._executors.get(record.key),
            )
            for record in records
        ]

        if workspace_id:
            sessions = [s for s in sessions if s.workspace_id == workspace_id]
        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]
        if status:
            sessions = [s for s in sessions if s.status == status]

        sessions.sort(key=lambda session: session.created_at, reverse=True)
        return sessions

    async def get_stats(self) -> dict[str, Any]:
        sessions = await self.list_sessions()
        status_counts: dict[str, int] = {}
        for session in sessions:
            status_counts[session.status] = status_counts.get(session.status, 0) + 1
        return {
            "total_sessions": len(sessions),
            "by_status": status_counts,
        }

    async def clear(self) -> None:
        for session_id, executor in list(self._executors.items()):
            if executor:
                try:
                    executor.reset()
                except Exception as exc:
                    self._logger.warning("Failed to reset executor %s: %s", session_id, exc)
        self._executors.clear()
        await self._store.clear(namespace=self.SESSION_NAMESPACE)
        self._logger.info("Cleared all sessions")

    def set_executor(self, session_id: str, executor: Any) -> None:
        self._executors[session_id] = executor

    def remove_executor(self, session_id: str) -> None:
        self._executors.pop(session_id, None)

    def get_executor(self, session_id: str) -> Any:
        return self._executors.get(session_id)

    def _generate_session_id(self) -> str:
        return f"sess-{uuid.uuid4().hex[:12]}"
