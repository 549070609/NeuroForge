"""
会话持久化系统

支持 JSONL 格式的会话存储、快照和回滚
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SessionMetadata(BaseModel):
    """会话元数据"""

    id: str
    created_at: str
    updated_at: str
    model: str = ""
    workspace: str = ""
    title: str = ""
    message_count: int = 0
    context_tokens: int = 0


class SessionState(BaseModel):
    """会话状态"""

    loaded_skills: list[str] = []
    variables: dict[str, Any] = {}
    last_activity: str = ""


class SessionSummary(BaseModel):
    """会话摘要"""

    summary: str = ""
    key_decisions: list[str] = []
    files_modified: list[str] = []
    tools_used: list[str] = []


@dataclass
class SessionSnapshot:
    """会话快照"""

    id: str
    timestamp: str
    description: str
    message_count: int
    messages: list[dict[str, Any]] = field(default_factory=list)


class SessionPersistence:
    """
    会话持久化管理器

    支持:
    - JSONL 格式消息存储
    - 会话元数据管理
    - 快照创建和回滚
    - 摘要存储
    """

    def __init__(
        self,
        sessions_dir: Path | str,
        session_id: str,
    ) -> None:
        """
        初始化持久化管理器

        Args:
            sessions_dir: 会话存储根目录
            session_id: 会话 ID
        """
        self.sessions_dir = Path(sessions_dir)
        self.session_id = session_id
        self.session_dir = self.sessions_dir / session_id

        # 确保目录存在
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "snapshots").mkdir(exist_ok=True)

        # 文件路径
        self.metadata_file = self.session_dir / "metadata.json"
        self.messages_file = self.session_dir / "messages.jsonl"
        self.state_file = self.session_dir / "state.json"
        self.summary_file = self.session_dir / "summary.json"

    def initialize(
        self,
        model: str = "",
        workspace: str = "",
        title: str = "",
    ) -> SessionMetadata:
        """
        初始化新会话

        Args:
            model: 使用的模型
            workspace: 工作空间路径
            title: 会话标题

        Returns:
            会话元数据
        """
        now = datetime.utcnow().isoformat() + "Z"

        metadata = SessionMetadata(
            id=self.session_id,
            created_at=now,
            updated_at=now,
            model=model,
            workspace=workspace,
            title=title,
        )

        self._save_metadata(metadata)

        # 初始化空的消息文件
        self.messages_file.write_text("", encoding="utf-8")

        # 初始化状态
        state = SessionState(last_activity=now)
        self._save_state(state)

        logger.info(
            "Initialized session",
            extra_data={"session_id": self.session_id, "dir": str(self.session_dir)},
        )

        return metadata

    def load_metadata(self) -> SessionMetadata | None:
        """加载会话元数据"""
        if not self.metadata_file.exists():
            return None

        try:
            data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
            return SessionMetadata(**data)
        except Exception as e:
            logger.error(
                "Failed to load metadata",
                extra_data={"error": str(e), "file": str(self.metadata_file)},
            )
            return None

    def _save_metadata(self, metadata: SessionMetadata) -> None:
        """保存会话元数据"""
        self.metadata_file.write_text(
            metadata.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def update_metadata(self, **updates: Any) -> None:
        """更新会话元数据"""
        metadata = self.load_metadata()
        if metadata:
            for key, value in updates.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)
            metadata.updated_at = datetime.utcnow().isoformat() + "Z"
            self._save_metadata(metadata)

    def append_message(self, message: dict[str, Any]) -> None:
        """
        追加消息到 JSONL 文件

        Args:
            message: 消息字典
        """
        with open(self.messages_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")

        # 更新消息计数
        self.update_metadata(message_count=self.count_messages())

    def read_messages(self) -> Iterator[dict[str, Any]]:
        """
        读取所有消息

        Yields:
            消息字典
        """
        if not self.messages_file.exists():
            return

        with open(self.messages_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    def get_messages_list(self) -> list[dict[str, Any]]:
        """获取消息列表"""
        return list(self.read_messages())

    def count_messages(self) -> int:
        """计算消息数量"""
        if not self.messages_file.exists():
            return 0

        count = 0
        with open(self.messages_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    def load_state(self) -> SessionState:
        """加载会话状态"""
        if not self.state_file.exists():
            return SessionState()

        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return SessionState(**data)
        except Exception:
            return SessionState()

    def _save_state(self, state: SessionState) -> None:
        """保存会话状态"""
        self.state_file.write_text(
            state.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def update_state(self, **updates: Any) -> None:
        """更新会话状态"""
        state = self.load_state()
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.last_activity = datetime.utcnow().isoformat() + "Z"
        self._save_state(state)

    def load_summary(self) -> SessionSummary | None:
        """加载会话摘要"""
        if not self.summary_file.exists():
            return None

        try:
            data = json.loads(self.summary_file.read_text(encoding="utf-8"))
            return SessionSummary(**data)
        except Exception:
            return None

    def save_summary(self, summary: SessionSummary) -> None:
        """保存会话摘要"""
        self.summary_file.write_text(
            summary.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def create_snapshot(
        self,
        description: str = "",
    ) -> SessionSnapshot:
        """
        创建会话快照

        Args:
            description: 快照描述

        Returns:
            快照对象
        """
        timestamp = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        snapshot_id = f"snap_{timestamp}"
        snapshot_file = self.session_dir / "snapshots" / f"{snapshot_id}.json"

        messages = self.get_messages_list()

        snapshot = SessionSnapshot(
            id=snapshot_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            description=description,
            message_count=len(messages),
            messages=messages,
        )

        snapshot_file.write_text(
            json.dumps(snapshot.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "Created snapshot",
            extra_data={
                "session_id": self.session_id,
                "snapshot_id": snapshot_id,
                "message_count": len(messages),
            },
        )

        return snapshot

    def load_snapshot(self, snapshot_id: str) -> SessionSnapshot | None:
        """
        加载快照

        Args:
            snapshot_id: 快照 ID

        Returns:
            快照对象或 None
        """
        snapshot_file = self.session_dir / "snapshots" / f"{snapshot_id}.json"

        if not snapshot_file.exists():
            return None

        try:
            data = json.loads(snapshot_file.read_text(encoding="utf-8"))
            return SessionSnapshot(**data)
        except Exception as e:
            logger.error(
                "Failed to load snapshot",
                extra_data={"snapshot_id": snapshot_id, "error": str(e)},
            )
            return None

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """
        从快照恢复会话

        Args:
            snapshot_id: 快照 ID

        Returns:
            是否成功
        """
        snapshot = self.load_snapshot(snapshot_id)
        if not snapshot:
            return False

        # 备份当前消息
        self.create_snapshot("pre-restore-backup")

        # 恢复消息
        with open(self.messages_file, "w", encoding="utf-8") as f:
            for msg in snapshot.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

        # 更新元数据
        self.update_metadata(message_count=len(snapshot.messages))

        logger.info(
            "Restored from snapshot",
            extra_data={
                "session_id": self.session_id,
                "snapshot_id": snapshot_id,
            },
        )

        return True

    def list_snapshots(self) -> list[dict[str, Any]]:
        """
        列出所有快照

        Returns:
            快照信息列表
        """
        snapshots_dir = self.session_dir / "snapshots"
        if not snapshots_dir.exists():
            return []

        snapshots = []
        for snapshot_file in sorted(snapshots_dir.glob("snap_*.json")):
            try:
                data = json.loads(snapshot_file.read_text(encoding="utf-8"))
                snapshots.append({
                    "id": data.get("id", snapshot_file.stem),
                    "timestamp": data.get("timestamp", ""),
                    "description": data.get("description", ""),
                    "message_count": data.get("message_count", 0),
                })
            except Exception:
                continue

        return snapshots

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照"""
        snapshot_file = self.session_dir / "snapshots" / f"{snapshot_id}.json"

        if snapshot_file.exists():
            snapshot_file.unlink()
            return True
        return False

    def delete_session(self) -> bool:
        """删除整个会话"""
        import shutil

        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)
            logger.info(
                "Deleted session",
                extra_data={"session_id": self.session_id},
            )
            return True
        return False


class SessionManager:
    """
    会话管理器

    管理多个会话的创建、列表和删除
    """

    def __init__(
        self,
        sessions_dir: Path | str = ".sessions",
    ) -> None:
        """
        初始化会话管理器

        Args:
            sessions_dir: 会话存储根目录
        """
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        model: str = "",
        workspace: str = "",
        title: str = "",
    ) -> SessionPersistence:
        """
        创建新会话

        Args:
            model: 使用的模型
            workspace: 工作空间路径
            title: 会话标题

        Returns:
            SessionPersistence 实例
        """
        import uuid

        session_id = f"session_{uuid.uuid4().hex[:12]}"
        persistence = SessionPersistence(self.sessions_dir, session_id)
        persistence.initialize(model=model, workspace=workspace, title=title)

        return persistence

    def load_session(self, session_id: str) -> SessionPersistence | None:
        """
        加载现有会话

        Args:
            session_id: 会话 ID

        Returns:
            SessionPersistence 实例或 None
        """
        persistence = SessionPersistence(self.sessions_dir, session_id)

        if not persistence.metadata_file.exists():
            return None

        return persistence

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        列出所有会话

        Returns:
            会话信息列表
        """
        sessions = []

        for session_dir in sorted(
            self.sessions_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if not session_dir.is_dir():
                continue

            metadata_file = session_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            try:
                data = json.loads(metadata_file.read_text(encoding="utf-8"))
                sessions.append({
                    "id": session_dir.name,
                    "title": data.get("title", ""),
                    "model": data.get("model", ""),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": data.get("message_count", 0),
                })
            except Exception:
                continue

        return sessions

    def get_recent_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取最近的会话"""
        return self.list_sessions()[:limit]

    def search_sessions(
        self,
        query: str = "",
        model: str = "",
    ) -> list[dict[str, Any]]:
        """
        搜索会话

        Args:
            query: 搜索关键词
            model: 模型过滤

        Returns:
            匹配的会话列表
        """
        sessions = self.list_sessions()
        results = []

        for session in sessions:
            # 模型过滤
            if model and session.get("model") != model:
                continue

            # 关键词搜索
            if query:
                title = session.get("title", "").lower()
                if query.lower() not in title:
                    continue

            results.append(session)

        return results
