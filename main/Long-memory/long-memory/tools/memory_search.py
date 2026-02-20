"""
记忆搜索工具
"""

from typing import Any, Dict, List, Optional
import json
from pyagentforge.kernel.base_tool import BaseTool

from ..vector_store import ChromaVectorStore
from ..config import LongMemoryConfig


class MemorySearchTool(BaseTool):
    """语义搜索长记忆"""

    name = "memory_search"
    description = """
在长记忆中进行语义搜索，查找与查询相关的记忆。

使用场景：
- 用户询问之前的偏好或设置
- 需要回顾之前的对话或决策
- 查找特定主题的相关记忆

搜索基于语义相似度，不是关键词匹配。
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询文本"
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量，默认 5",
                "default": 5,
                "minimum": 1,
                "maximum": 50
            },
            "session_filter": {
                "type": "string",
                "description": "按会话 ID 过滤（可选）"
            },
            "type_filter": {
                "type": "string",
                "enum": ["user", "assistant", "tool", "summary", "knowledge"],
                "description": "按消息类型过滤（可选）"
            },
            "min_importance": {
                "type": "number",
                "description": "最低重要性过滤 0.0-1.0",
                "minimum": 0,
                "maximum": 1
            }
        },
        "required": ["query"]
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
        query: str,
        limit: int = 5,
        session_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        min_importance: Optional[float] = None,
    ) -> str:
        """搜索记忆"""
        # 构建过滤条件
        where = None
        conditions = []

        if session_filter:
            conditions.append({"session_id": session_filter})
        if type_filter:
            conditions.append({"message_type": type_filter})
        if min_importance is not None:
            conditions.append({"importance": {"$gte": min_importance}})

        if conditions:
            if len(conditions) == 1:
                where = conditions[0]
            else:
                where = {"$and": conditions}

        # 执行搜索
        results = await self._store.search(
            query=query,
            n_results=limit,
            where=where,
        )

        if not results:
            return "未找到相关记忆"

        # 格式化输出
        output_lines = [f"找到 {len(results)} 条相关记忆:\n"]

        for i, result in enumerate(results, 1):
            entry = result.entry
            output_lines.append(
                f"{i}. [相似度: {result.score:.2%}] {entry.content[:150]}{'...' if len(entry.content) > 150 else ''}"
            )
            output_lines.append(
                f"   ID: {entry.id} | 类型: {entry.message_type.value} | 重要性: {entry.importance:.2f} | 时间: {entry.timestamp[:10]}"
            )
            if entry.tags:
                output_lines.append(f"   标签: {', '.join(entry.tags)}")
            output_lines.append("")

        return "\n".join(output_lines)
