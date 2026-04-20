"""
批量重加工工具

处理未加工的历史记忆
"""

from typing import List, Optional
from pyagentforge.tools.base import BaseTool

from ..processor_engine import ProcessorEngine


class MemoryReprocessTool(BaseTool):
    """批量重加工记忆"""

    name = "memory_reprocess"
    description = """
批量处理历史记忆，为缺少标签、主题或摘要的记忆自动生成元数据。

使用场景：
- 首次启用记忆加工功能后，处理现有历史记忆
- 批量优化大量未加工的记忆
- 按条件筛选后批量重加工

该工具会：
1. 查找缺少元数据的记忆
2. 分析内容生成标签、主题、摘要
3. 更新存储
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "最大处理数量，默认 10",
                "default": 10,
                "minimum": 1,
                "maximum": 100
            },
            "filter_tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "只处理包含这些标签的记忆（可选）",
                "default": []
            },
            "filter_topic": {
                "type": "string",
                "description": "只处理主题匹配的记忆（可选）",
                "default": ""
            }
        },
        "required": []
    }
    timeout = 300  # 批量处理需要更长时间
    risk_level = "low"

    def __init__(self, engine: ProcessorEngine):
        super().__init__()
        self._engine = engine

    async def execute(
        self,
        limit: int = 10,
        filter_tags: Optional[List[str]] = None,
        filter_topic: Optional[str] = None,
    ) -> str:
        """执行批量加工"""
        # 根据是否有过滤条件选择方法
        if filter_tags or filter_topic:
            results = await self._engine.reprocess_by_filter(
                filter_tags=filter_tags,
                filter_topic=filter_topic,
                limit=limit,
            )
        else:
            results = await self._engine.reprocess_unprocessed(limit=limit)

        if not results:
            return "没有找到需要加工的记忆"

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count

        # 格式化输出
        lines = [
            f"批量加工完成: {success_count} 成功, {fail_count} 失败",
            "",
            "--- 处理详情 ---",
        ]

        for result in results[:10]:  # 最多显示 10 条详情
            status = "✓" if result.success else "✗"
            if result.success and result.analysis:
                tags_str = f"[{', '.join(result.analysis.tags)}]" if result.analysis.tags else ""
                topic_str = f"主题: {result.analysis.topic}" if result.analysis.topic else ""
                lines.append(
                    f"{status} {result.memory_id}: {tags_str} {topic_str}".strip()
                )
            else:
                lines.append(f"{status} {result.memory_id}: {result.error}")

        if len(results) > 10:
            lines.append(f"... 还有 {len(results) - 10} 条未显示")

        # 方法统计
        method_counts = {}
        for r in results:
            if r.success and r.analysis:
                method = r.analysis.method
                method_counts[method] = method_counts.get(method, 0) + 1

        if method_counts:
            lines.append("")
            lines.append("分析方法统计:")
            for method, count in method_counts.items():
                lines.append(f"  - {method}: {count} 条")

        return "\n".join(lines)
