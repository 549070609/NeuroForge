"""
记忆列表和统计工具
"""

from typing import Any, Dict, List, Optional
import json
from pyagentforge.kernel.base_tool import BaseTool

from ..vector_store import ChromaVectorStore
from ..config import LongMemoryConfig


class MemoryListTool(BaseTool):
    """列出记忆和获取统计"""

    name = "memory_list"
    description = """
列出长记忆系统中的记忆，或获取统计信息。

使用场景：
- 查看存储了哪些记忆
- 获取记忆系统概览
- 按条件筛选记忆
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "stats"],
                "description": "操作类型: list=列出记忆, stats=获取统计",
                "default": "list"
            },
            "limit": {
                "type": "integer",
                "description": "返回数量限制（仅 list 模式），默认 10",
                "default": 10,
                "minimum": 1,
                "maximum": 100
            },
            "offset": {
                "type": "integer",
                "description": "偏移量（仅 list 模式），用于分页",
                "default": 0,
                "minimum": 0
            },
            "session_filter": {
                "type": "string",
                "description": "按会话 ID 过滤（可选）"
            }
        },
        "required": []
    }
    timeout = 30
    risk_level = "low"

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
        action: str = "list",
        limit: int = 10,
        offset: int = 0,
        session_filter: Optional[str] = None,
    ) -> str:
        """列出记忆或获取统计"""

        if action == "stats":
            return await self._get_stats()

        return await self._list_memories(limit, offset, session_filter)

    async def _get_stats(self) -> str:
        """获取统计信息"""
        stats = await self._store.get_stats()

        lines = [
            "长记忆系统统计信息",
            "=" * 40,
            f"总记忆数: {stats.total_count}",
            f"唯一会话数: {stats.unique_sessions}",
            f"平均重要性: {stats.avg_importance:.3f}",
        ]

        if stats.oldest_timestamp:
            lines.append(f"最早记忆: {stats.oldest_timestamp[:10]}")
        if stats.newest_timestamp:
            lines.append(f"最新记忆: {stats.newest_timestamp[:10]}")

        if stats.by_type:
            lines.append("\n按类型统计:")
            for t, c in sorted(stats.by_type.items(), key=lambda x: -x[1]):
                lines.append(f"  {t}: {c}")

        if stats.by_source:
            lines.append("\n按来源统计:")
            for s, c in sorted(stats.by_source.items(), key=lambda x: -x[1]):
                lines.append(f"  {s}: {c}")

        return "\n".join(lines)

    async def _list_memories(
        self,
        limit: int,
        offset: int,
        session_filter: Optional[str],
    ) -> str:
        """列出记忆"""
        where = None
        if session_filter:
            where = {"session_id": session_filter}

        memories = await self._store.list_memories(
            limit=limit,
            offset=offset,
            where=where,
        )

        if not memories:
            return "没有找到记忆"

        lines = [f"记忆列表 (显示 {len(memories)} 条, 偏移 {offset}):\n"]

        for i, entry in enumerate(memories, offset + 1):
            lines.append(
                f"{i}. {entry.content[:100]}{'...' if len(entry.content) > 100 else ''}"
            )
            lines.append(
                f"   ID: {entry.id} | 类型: {entry.message_type.value} | "
                f"重要性: {entry.importance:.2f} | {entry.timestamp[:10]}"
            )
            if entry.tags:
                lines.append(f"   标签: {', '.join(entry.tags)}")
            lines.append("")

        return "\n".join(lines)
