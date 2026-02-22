"""
记忆搜索工具

支持两种搜索模式：
- fuzzy (模糊): 语义相似度搜索，基于向量嵌入
- exact (精准): 关键词/文本精确匹配
"""

from typing import Any, Dict, List, Literal, Optional
import json
from pyagentforge.kernel.base_tool import BaseTool

from ..vector_store import ChromaVectorStore
from ..config import LongMemoryConfig


class MemorySearchTool(BaseTool):
    """搜索长记忆"""

    name = "memory_search"
    description = """
在长记忆中搜索，支持两种模式：

1. 模糊模式 (fuzzy): 语义相似度搜索
   - 基于向量嵌入，理解语义含义
   - 适合查找相关主题，即使用词不同
   - 例如: "用户喜欢什么" 能匹配 "我爱吃苹果"

2. 精准模式 (exact): 关键词精确匹配
   - 文本内容必须包含查询词
   - 适合查找特定词句、代码、配置等
   - 例如: "API_KEY" 只匹配包含 "API_KEY" 的记忆

使用场景：
- 用户询问偏好、设置 → fuzzy
- 查找特定代码片段、配置值 → exact
- 不确定用哪个 → 默认 fuzzy
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询文本"
            },
            "mode": {
                "type": "string",
                "enum": ["fuzzy", "exact"],
                "default": "fuzzy",
                "description": """搜索模式:
- fuzzy: 模糊搜索（语义相似度），适合理解性查询
- exact: 精准搜索（关键词匹配），适合精确查找"""
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
        mode: Literal["fuzzy", "exact"] = "fuzzy",
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
            mode=mode,
        )

        if not results:
            mode_desc = "精准" if mode == "exact" else "模糊"
            return f"在{mode_desc}模式下未找到相关记忆"

        # 格式化输出
        mode_desc = "精准匹配" if mode == "exact" else "语义相似"
        output_lines = [f"找到 {len(results)} 条相关记忆 ({mode_desc}):\n"]

        for i, result in enumerate(results, 1):
            entry = result.entry
            output_lines.append(
                f"{i}. [匹配度: {result.score:.2%}] {entry.content[:150]}{'...' if len(entry.content) > 150 else ''}"
            )
            output_lines.append(
                f"   ID: {entry.id} | 类型: {entry.message_type.value} | 重要性: {entry.importance:.2f} | 时间: {entry.timestamp[:10]}"
            )
            if entry.tags:
                output_lines.append(f"   标签: {', '.join(entry.tags)}")
            output_lines.append("")

        return "\n".join(output_lines)
