"""
记忆删除工具
"""

from typing import List, Optional
from pyagentforge.tools.base import BaseTool

try:
    from ..vector_store import ChromaVectorStore
    from ..config import LongMemoryConfig
except ImportError:
    from vector_store import ChromaVectorStore
    from config import LongMemoryConfig


class MemoryDeleteTool(BaseTool):
    """删除长记忆"""

    name = "memory_delete"
    description = """
从长记忆系统中删除记忆。

使用场景：
- 用户要求忘记某些信息
- 记忆已过时或不再需要
- 清理错误或无效的记忆

警告：删除操作不可逆，请谨慎使用。
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "memory_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要删除的记忆 ID 列表"
            },
            "session_filter": {
                "type": "string",
                "description": "删除指定会话的所有记忆（与 memory_ids 互斥）"
            },
            "type_filter": {
                "type": "string",
                "enum": ["user", "assistant", "tool", "summary", "knowledge"],
                "description": "按消息类型删除（与 session_filter 配合使用）"
            },
            "confirm": {
                "type": "boolean",
                "description": "确认删除，必须为 true",
                "default": False
            }
        },
        "required": ["confirm"]
    }
    timeout = 30
    risk_level = "medium"  # 删除操作风险较高

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        config: LongMemoryConfig,
    ):
        super().__init__()
        self._store = vector_store
        self._config = config

    async def execute(
        self,
        confirm: bool,
        memory_ids: Optional[List[str]] = None,
        session_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> str:
        """删除记忆"""
        if not confirm:
            return "删除操作未确认。请设置 confirm=true 来执行删除。"

        if not memory_ids and not session_filter:
            return "请指定要删除的记忆 ID (memory_ids) 或会话过滤条件 (session_filter)"

        # 按 ID 删除
        if memory_ids:
            count = await self._store.delete(ids=memory_ids)
            return f"已删除 {count} 条记忆\n删除的 ID: {', '.join(memory_ids[:10])}{'...' if len(memory_ids) > 10 else ''}"

        # 按条件删除
        where = None
        conditions = []

        if session_filter:
            conditions.append({"session_id": session_filter})
        if type_filter:
            conditions.append({"message_type": type_filter})

        if conditions:
            if len(conditions) == 1:
                where = conditions[0]
            else:
                where = {"$and": conditions}

        count = await self._store.delete(where=where)

        filter_desc = []
        if session_filter:
            filter_desc.append(f"会话 {session_filter}")
        if type_filter:
            filter_desc.append(f"类型 {type_filter}")

        return f"已删除 {count} 条记忆\n过滤条件: {', '.join(filter_desc)}"
