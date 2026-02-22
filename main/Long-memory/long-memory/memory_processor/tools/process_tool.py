"""
手动加工工具

处理指定记忆 ID 的加工
"""

from typing import Optional
from pyagentforge.kernel.base_tool import BaseTool

from ..processor_engine import ProcessorEngine


class MemoryProcessTool(BaseTool):
    """手动加工指定记忆"""

    name = "memory_process"
    description = """
处理并优化指定记忆的元数据（标签、主题、摘要）。

使用场景：
- 手动优化某条记忆的分类信息
- 重新生成记忆的摘要和主题
- 为记忆添加标签

该工具会分析记忆内容，自动生成：
- 标签: 从预定义标签池选择
- 主题: 3-5 个字的概括
- 摘要: 1-2 句话的内容摘要
"""
    parameters_schema = {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "要加工的记忆 ID（格式: mem_xxx）"
            },
            "force": {
                "type": "boolean",
                "description": "是否强制重新加工（即使已有标签/主题）",
                "default": False
            }
        },
        "required": ["memory_id"]
    }
    timeout = 60
    risk_level = "low"

    def __init__(self, engine: ProcessorEngine):
        super().__init__()
        self._engine = engine

    async def execute(
        self,
        memory_id: str,
        force: bool = False,
    ) -> str:
        """执行加工"""
        result = await self._engine.process_by_id(memory_id, force=force)

        if not result.success:
            return f"加工失败: {result.error}"

        # 格式化输出
        lines = [
            f"记忆加工完成 (ID: {memory_id})",
            "",
        ]

        if result.analysis:
            analysis = result.analysis
            lines.append(f"分析方法: {analysis.method}")
            lines.append(f"置信度: {analysis.confidence:.2f}")
            lines.append("")

            if analysis.tags:
                lines.append(f"标签: {', '.join(analysis.tags)}")

            if analysis.topic:
                lines.append(f"主题: {analysis.topic}")

            if analysis.summary:
                lines.append(f"摘要: {analysis.summary}")

        # 显示变更
        if result.original_entry and result.updated_entry:
            lines.append("")
            lines.append("--- 变更详情 ---")

            if result.original_entry.tags != result.updated_entry.tags:
                lines.append(
                    f"标签: {result.original_entry.tags or '(无)'} → {result.updated_entry.tags}"
                )

            if result.original_entry.topic != result.updated_entry.topic:
                lines.append(
                    f"主题: {result.original_entry.topic or '(无)'} → {result.updated_entry.topic}"
                )

            if not result.original_entry.summary and result.updated_entry.summary:
                lines.append(f"摘要: (新增) {result.updated_entry.summary}")

        return "\n".join(lines)
