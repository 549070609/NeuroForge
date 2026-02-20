"""
长记忆数据模型

定义记忆条目、搜索结果和相关枚举类型
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
import json


class MessageType(str, Enum):
    """消息类型"""
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SUMMARY = "summary"
    KNOWLEDGE = "knowledge"


class MemorySource(str, Enum):
    """记忆来源"""
    MANUAL = "manual"       # 手动存储
    AUTO = "auto"           # 自动存储（通过工具调用）
    SESSION = "session"     # 会话自动记录


@dataclass
class MemoryEntry:
    """记忆条目"""

    content: str                            # 记忆内容
    timestamp: str = ""                     # ISO8601 时间戳
    id: str = ""                            # 唯一标识 mem_xxx
    session_id: str = ""                    # 会话 ID
    message_type: MessageType = MessageType.USER
    source: MemorySource = MemorySource.MANUAL
    importance: float = 0.5                 # 重要性 0.0-1.0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if not self.id:
            self.id = f"mem_{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
        # 确保 message_type 和 source 是枚举类型
        if isinstance(self.message_type, str):
            self.message_type = MessageType(self.message_type)
        if isinstance(self.source, str):
            self.source = MemorySource(self.source)
        # 限制 importance 范围
        self.importance = max(0.0, min(1.0, self.importance))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 ChromaDB metadata）"""
        return {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "message_type": self.message_type.value,
            "source": self.source.value,
            "importance": self.importance,
            "tags": json.dumps(self.tags, ensure_ascii=False),
            "metadata": json.dumps(self.metadata, ensure_ascii=False),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """从字典创建"""
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", ""),
            session_id=data.get("session_id", ""),
            message_type=MessageType(data.get("message_type", "user")),
            source=MemorySource(data.get("source", "manual")),
            importance=float(data.get("importance", 0.5)),
            tags=json.loads(data.get("tags", "[]")),
            metadata=json.loads(data.get("metadata", "{}")),
        )

    def __str__(self) -> str:
        return f"MemoryEntry(id={self.id}, type={self.message_type.value}, importance={self.importance:.2f})"


@dataclass
class MemorySearchResult:
    """记忆搜索结果"""

    entry: MemoryEntry                      # 记忆条目
    score: float = 0.0                      # 相似度分数 (0-1)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.entry.id,
            "content": self.entry.content,
            "score": round(self.score, 4),
            "timestamp": self.entry.timestamp,
            "session_id": self.entry.session_id,
            "message_type": self.entry.message_type.value,
            "source": self.entry.source.value,
            "importance": self.entry.importance,
            "tags": self.entry.tags,
            "metadata": self.entry.metadata,
        }

    def __str__(self) -> str:
        return f"MemorySearchResult(id={self.entry.id}, score={self.score:.4f})"


@dataclass
class MemoryStats:
    """记忆统计信息"""

    total_count: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    avg_importance: float = 0.0
    oldest_timestamp: str = ""
    newest_timestamp: str = ""
    unique_sessions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_count": self.total_count,
            "by_type": self.by_type,
            "by_source": self.by_source,
            "avg_importance": round(self.avg_importance, 3),
            "oldest_timestamp": self.oldest_timestamp,
            "newest_timestamp": self.newest_timestamp,
            "unique_sessions": self.unique_sessions,
        }
