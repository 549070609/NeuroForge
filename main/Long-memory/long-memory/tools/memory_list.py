"""
记忆列表和统计工具

支持按标签、主题、时间的组合过滤召回记忆
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import re
from pyagentforge.kernel.base_tool import BaseTool

from ..vector_store import ChromaVectorStore
from ..config import LongMemoryConfig


class MemoryListTool(BaseTool):
    """列出记忆和获取统计"""

    name = "memory_list"
    description = """
按条件召回记忆列表，支持标签、主题、时间的任意组合过滤。

过滤条件（可组合使用 1-3 个）：
- tags: 标签列表，匹配任意一个标签即可
- topic: 记忆主题，精确匹配
- time_range: 时间范围，如 "2024-01-01~2024-12-31" 或 "最近7天"

使用场景：
- 查看特定主题的所有记忆
- 查找特定时间段内的记忆
- 按标签分类浏览记忆
- 组合条件精确定位记忆
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "stats", "recall"],
                "description": """操作类型:
- list: 列出记忆（简单分页）
- stats: 获取统计信息
- recall: 按条件组合过滤召回""",
                "default": "list"
            },
            "limit": {
                "type": "integer",
                "description": "返回数量限制，默认 10",
                "default": 10,
                "minimum": 1,
                "maximum": 100
            },
            "offset": {
                "type": "integer",
                "description": "偏移量，用于分页",
                "default": 0,
                "minimum": 0
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "按标签过滤（匹配任意一个即可）",
                "examples": [["偏好", "设置"], ["代码", "项目"]]
            },
            "topic": {
                "type": "string",
                "description": "按主题精确匹配"
            },
            "time_range": {
                "type": "string",
                "description": """时间范围过滤，支持格式:
- 日期范围: "2024-01-01~2024-12-31"
- 相对时间: "今天", "昨天", "最近7天", "最近30天", "本周", "本月"
- 单个日期: "2024-01-15"（当天）""",
                "examples": ["最近7天", "2024-01-01~2024-12-31"]
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
        tags: Optional[List[str]] = None,
        topic: Optional[str] = None,
        time_range: Optional[str] = None,
        session_filter: Optional[str] = None,
    ) -> str:
        """列出记忆或获取统计"""

        if action == "stats":
            return await self._get_stats()

        if action == "recall":
            return await self._recall_memories(
                limit=limit,
                offset=offset,
                tags=tags,
                topic=topic,
                time_range=time_range,
                session_filter=session_filter,
            )

        return await self._list_memories(limit, offset, session_filter)

    def _parse_time_range(self, time_range: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析时间范围字符串

        Args:
            time_range: 时间范围字符串

        Returns:
            (start_date, end_date) 元组，ISO 格式字符串
        """
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 相对时间
        relative_times = {
            "今天": (today, today + timedelta(days=1)),
            "昨天": (today - timedelta(days=1), today),
            "最近7天": (today - timedelta(days=7), now),
            "最近30天": (today - timedelta(days=30), now),
            "本周": (today - timedelta(days=today.weekday()), now),
            "本月": (today.replace(day=1), now),
        }

        if time_range in relative_times:
            start, end = relative_times[time_range]
            return start.isoformat(), end.isoformat()

        # 日期范围: "2024-01-01~2024-12-31"
        if "~" in time_range:
            parts = time_range.split("~")
            if len(parts) == 2:
                try:
                    start = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
                    end = datetime.strptime(parts[1].strip(), "%Y-%m-%d")
                    end = end.replace(hour=23, minute=59, second=59)
                    return start.isoformat(), end.isoformat()
                except ValueError:
                    pass

        # 单个日期: "2024-01-15"
        try:
            date = datetime.strptime(time_range.strip(), "%Y-%m-%d")
            return date.isoformat(), (date + timedelta(days=1)).isoformat()
        except ValueError:
            pass

        return None, None

    async def _recall_memories(
        self,
        limit: int,
        offset: int,
        tags: Optional[List[str]],
        topic: Optional[str],
        time_range: Optional[str],
        session_filter: Optional[str],
    ) -> str:
        """按条件组合召回记忆"""
        # 解析时间范围
        start_time, end_time = None, None
        if time_range:
            start_time, end_time = self._parse_time_range(time_range)

        # 获取所有记忆（ChromaDB 不支持复杂过滤，需要客户端过滤）
        # 先用 ChromaDB 的 where 进行简单过滤
        where_conditions = []

        if session_filter:
            where_conditions.append({"session_id": session_filter})

        if topic:
            where_conditions.append({"topic": topic})

        where = None
        if len(where_conditions) == 1:
            where = where_conditions[0]
        elif len(where_conditions) > 1:
            where = {"$and": where_conditions}

        # 获取更多记忆用于客户端过滤
        fetch_limit = min(500, limit * 10)

        results = self._store._collection.get(
            where=where,
            limit=fetch_limit,
            include=["documents", "metadatas"]
        )

        # 客户端过滤
        filtered_entries = []
        if results["ids"]:
            for i, memory_id in enumerate(results["ids"]):
                try:
                    metadata = results["metadatas"][i]
                    entry = type(
                        "MemoryEntry", (), {}
                    )()  # 临时对象，用于过滤检查

                    # 从 metadata 创建 entry
                    from ..models import MemoryEntry
                    entry = MemoryEntry.from_dict(metadata)

                    # 标签过滤（匹配任意一个）
                    if tags:
                        entry_tags = set(entry.tags)
                        filter_tags = set(tags)
                        if not entry_tags.intersection(filter_tags):
                            continue

                    # 时间范围过滤
                    if start_time and end_time:
                        if entry.timestamp:
                            if not (start_time <= entry.timestamp < end_time):
                                continue

                    filtered_entries.append(entry)
                except Exception as e:
                    continue

        # 应用 offset 和 limit
        total_count = len(filtered_entries)
        start_idx = min(offset, total_count)
        end_idx = min(offset + limit, total_count)
        paginated_entries = filtered_entries[start_idx:end_idx]

        # 构建过滤条件描述
        filter_desc = []
        if tags:
            filter_desc.append(f"标签: {', '.join(tags)}")
        if topic:
            filter_desc.append(f"主题: {topic}")
        if time_range:
            filter_desc.append(f"时间: {time_range}")
        if session_filter:
            filter_desc.append(f"会话: {session_filter[:8]}...")

        if not paginated_entries:
            filter_str = " | ".join(filter_desc) if filter_desc else "无过滤条件"
            return f"未找到匹配的记忆\n过滤条件: {filter_str}"

        # 格式化输出
        filter_str = " | ".join(filter_desc) if filter_desc else "全部"
        lines = [
            f"召回记忆 (共 {total_count} 条，显示 {len(paginated_entries)} 条)",
            f"过滤条件: {filter_str}",
            ""
        ]

        for i, entry in enumerate(paginated_entries, offset + 1):
            lines.append(
                f"{i}. {entry.content[:100]}{'...' if len(entry.content) > 100 else ''}"
            )
            detail_parts = [f"ID: {entry.id}"]
            if entry.topic:
                detail_parts.append(f"主题: {entry.topic}")
            detail_parts.append(f"重要性: {entry.importance:.2f}")
            detail_parts.append(entry.timestamp[:10] if entry.timestamp else "无时间")
            lines.append(f"   {' | '.join(detail_parts)}")
            if entry.tags:
                lines.append(f"   标签: {', '.join(entry.tags)}")
            lines.append("")

        return "\n".join(lines)

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

        if stats.by_topic:
            lines.append("\n按主题统计:")
            for t, c in sorted(stats.by_topic.items(), key=lambda x: -x[1]):
                lines.append(f"  {t}: {c}")

        if stats.by_tag:
            lines.append("\n按标签统计:")
            # 只显示前 10 个标签
            sorted_tags = sorted(stats.by_tag.items(), key=lambda x: -x[1])[:10]
            for t, c in sorted_tags:
                lines.append(f"  {t}: {c}")
            if len(stats.by_tag) > 10:
                lines.append(f"  ... 还有 {len(stats.by_tag) - 10} 个标签")

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
            detail_parts = [f"ID: {entry.id}"]
            if entry.topic:
                detail_parts.append(f"主题: {entry.topic}")
            detail_parts.append(f"类型: {entry.message_type.value}")
            detail_parts.append(f"重要性: {entry.importance:.2f}")
            detail_parts.append(entry.timestamp[:10] if entry.timestamp else "")
            lines.append(f"   {' | '.join(detail_parts)}")
            if entry.tags:
                lines.append(f"   标签: {', '.join(entry.tags)}")
            lines.append("")

        return "\n".join(lines)
