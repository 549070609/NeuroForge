"""
Checkpoint 系统

支持 Agent 执行状态的持久化和崩溃恢复。
提供 BaseCheckpointer 接口和 FileCheckpointer 实现。
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Checkpoint:
    """Agent 执行的快照"""

    session_id: str
    iteration: int
    context_data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            session_id=data["session_id"],
            iteration=data["iteration"],
            context_data=data["context_data"],
            timestamp=data.get("timestamp", 0.0),
            metadata=data.get("metadata", {}),
        )


class BaseCheckpointer(ABC):
    """Checkpoint 存储后端的抽象基类"""

    @abstractmethod
    async def save(self, session_id: str, checkpoint: Checkpoint) -> None:
        """保存 checkpoint"""

    @abstractmethod
    async def load(self, session_id: str) -> Checkpoint | None:
        """加载最近一次 checkpoint"""

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """删除 session 的所有 checkpoint"""

    @abstractmethod
    async def list_sessions(self) -> list[str]:
        """列出所有有 checkpoint 的 session"""

    async def exists(self, session_id: str) -> bool:
        """检查 session 是否有 checkpoint"""
        return (await self.load(session_id)) is not None


class FileCheckpointer(BaseCheckpointer):
    """基于文件系统的 Checkpoint 存储

    每个 session 一个 JSON 文件，适合开发和小规模部署。
    """

    def __init__(self, directory: str | Path = ".checkpoints") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        logger.info(
            "FileCheckpointer initialized",
            extra_data={"directory": str(self.directory)},
        )

    def _path_for(self, session_id: str) -> Path:
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return self.directory / f"{safe_id}.json"

    async def save(self, session_id: str, checkpoint: Checkpoint) -> None:
        path = self._path_for(session_id)
        data = checkpoint.to_dict()
        path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")
        logger.debug(
            "Checkpoint saved",
            extra_data={
                "session_id": session_id,
                "iteration": checkpoint.iteration,
            },
        )

    async def load(self, session_id: str) -> Checkpoint | None:
        path = self._path_for(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Checkpoint.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "Failed to load checkpoint",
                extra_data={"session_id": session_id, "error": str(e)},
            )
            return None

    async def delete(self, session_id: str) -> None:
        path = self._path_for(session_id)
        if path.exists():
            path.unlink()
            logger.debug("Checkpoint deleted", extra_data={"session_id": session_id})

    async def list_sessions(self) -> list[str]:
        return [p.stem for p in self.directory.glob("*.json")]


class MemoryCheckpointer(BaseCheckpointer):
    """内存 Checkpoint 存储，适合测试。"""

    def __init__(self) -> None:
        self._store: dict[str, Checkpoint] = {}

    async def save(self, session_id: str, checkpoint: Checkpoint) -> None:
        self._store[session_id] = checkpoint

    async def load(self, session_id: str) -> Checkpoint | None:
        return self._store.get(session_id)

    async def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    async def list_sessions(self) -> list[str]:
        return list(self._store.keys())
