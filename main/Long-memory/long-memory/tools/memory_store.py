"""
记忆存储工具
"""

from typing import Any, Dict, List, Optional
from pyagentforge.kernel.base_tool import BaseTool

from ..models import MemoryEntry, MessageType, MemorySource
from ..vector_store import ChromaVectorStore
from ..config import LongMemoryConfig


class MemoryStoreTool(BaseTool):
    """存储记忆到向量数据库"""

    name = "memory_store"
    description = """
将信息存储到长记忆系统中，用于后续检索。

使用场景：
- 用户明确要求记住某些信息（"记住..."、"别忘了..."）
- 重要的用户偏好或设置
- 需要跨会话保留的知识或事实
- 任务关键信息

注意：不是所有对话都需要存储，只在明确重要时使用。
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要存储的记忆内容"
            },
            "topic": {
                "type": "string",
                "description": "记忆主题（用于分类和召回）",
                "examples": ["用户偏好", "项目配置", "代码片段", "学习笔记"]
            },
            "importance": {
                "type": "number",
                "description": "重要性分数 0.0-1.0，默认 0.5。越高越重要。",
                "default": 0.5,
                "minimum": 0,
                "maximum": 1
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "分类标签，用于后续过滤",
                "default": [],
                "examples": [["偏好", "设置"], ["代码", "Python"], ["重要"]]
            },
            "message_type": {
                "type": "string",
                "enum": ["user", "assistant", "tool", "summary", "knowledge"],
                "description": "消息类型，默认 'knowledge'",
                "default": "knowledge"
            }
        },
        "required": ["content"]
    }
    timeout = 30
    risk_level = "low"

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        config: LongMemoryConfig,
        session_id: str = "",
    ):
        super().__init__()
        self._store = vector_store
        self._config = config
        self._session_id = session_id

    async def execute(
        self,
        content: str,
        topic: Optional[str] = None,
        importance: float = 0.5,
        tags: List[str] = None,
        message_type: str = "knowledge",
    ) -> str:
        """存储记忆"""
        if tags is None:
            tags = []

        # 创建记忆条目
        entry = MemoryEntry(
            content=content,
            session_id=self._session_id,
            topic=topic or "",
            message_type=MessageType(message_type),
            source=MemorySource.MANUAL,
            importance=importance,
            tags=tags,
        )

        # 存储
        memory_id = await self._store.store(entry)

        # 格式化输出
        result_parts = [f"已存储记忆 (ID: {memory_id})"]
        if topic:
            result_parts.append(f"主题: {topic}")
        result_parts.append(f"内容: {content[:100]}{'...' if len(content) > 100 else ''}")
        result_parts.append(f"重要性: {importance:.2f}")
        if tags:
            result_parts.append(f"标签: {', '.join(tags)}")

        return "\n".join(result_parts)
