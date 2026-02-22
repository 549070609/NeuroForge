"""
超级压缩工具

提供手动压缩和状态查看工具
"""

from typing import Any, Optional
import logging

from pyagentforge.kernel.base_tool import BaseTool

from ..compress_engine import CompressEngine
from ..budget_manager import TokenBudgetManager

logger = logging.getLogger(__name__)


class CompressTool(BaseTool):
    """手动压缩工具"""

    name = "compress"
    description = "手动压缩当前对话历史。当上下文接近限制或需要清理历史时使用。压缩后的摘要会保存到长记忆中，可以随时召回。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "force": {
                "type": "boolean",
                "description": "强制压缩，即使未达到阈值",
                "default": False,
            },
            "keep_recent": {
                "type": "integer",
                "description": "保留最近的消息数量",
                "default": 20,
            },
            "store_to_memory": {
                "type": "boolean",
                "description": "是否将摘要存储到长记忆",
                "default": True,
            },
        },
        "required": [],
    }

    def __init__(
        self,
        engine: CompressEngine,
        get_messages_func: callable,
        set_messages_func: callable,
    ):
        super().__init__()
        self.engine = engine
        self.get_messages = get_messages_func
        self.set_messages = set_messages_func

    async def execute(
        self,
        force: bool = False,
        keep_recent: int = 20,
        store_to_memory: bool = True,
    ) -> str:
        """执行压缩"""
        # 临时更新 keep_recent
        original_keep = self.engine.keep_recent
        self.engine.keep_recent = keep_recent

        try:
            # 获取当前消息
            messages = self.get_messages()

            if not messages:
                return "没有消息需要压缩。"

            # 执行压缩
            result = await self.engine.compress(
                messages=messages,
                force=force,
                store_to_memory=store_to_memory,
            )

            # 更新消息
            self.set_messages(result.compressed_messages)

            # 格式化输出
            lines = [
                "## 压缩完成",
                "",
                f"- **原始消息数**: {result.original_count}",
                f"- **压缩后消息数**: {result.compressed_count}",
                f"- **原始 Token 数**: {result.original_tokens:,}",
                f"- **压缩后 Token 数**: {result.compressed_tokens:,}",
                f"- **压缩比**: {result.compression_ratio:.1%}",
                f"- **摘要已存储**: {'是' if result.summary_stored else '否'}",
            ]

            if result.summary_id:
                lines.append(f"- **摘要 ID**: {result.summary_id}")
                lines.append("")
                lines.append("可以使用 `memory_recall` 工具来查询历史信息。")

            return "\n".join(lines)

        finally:
            # 恢复原始设置
            self.engine.keep_recent = original_keep


class CompressStatusTool(BaseTool):
    """压缩状态工具"""

    name = "compress_status"
    description = "查看当前对话的 Token 预算和压缩状态。帮助判断是否需要手动压缩。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "preview": {
                "type": "boolean",
                "description": "是否显示压缩预览",
                "default": True,
            },
        },
        "required": [],
    }

    def __init__(
        self,
        budget_manager: TokenBudgetManager,
        engine: CompressEngine,
        get_messages_func: callable,
    ):
        super().__init__()
        self.budget_manager = budget_manager
        self.engine = engine
        self.get_messages = get_messages_func

    async def execute(self, preview: bool = True) -> str:
        """查看状态"""
        messages = self.get_messages()

        # 获取预算状态
        status = self.budget_manager.get_budget_status(messages)

        lines = [status, ""]

        # 添加压缩预览
        if preview:
            preview_info = self.engine.get_compress_preview(messages)

            lines.append("## 压缩预览")
            lines.append("")
            lines.append(f"- **需要压缩**: {'是' if preview_info['should_compress'] else '否'}")
            lines.append(f"- **总消息数**: {preview_info['split']['total_messages']}")
            lines.append(f"- **待压缩**: {preview_info['split']['to_compress']}")
            lines.append(f"- **保留**: {preview_info['split']['to_keep']}")
            lines.append(
                f"- **预计节省**: ~{preview_info['estimated_savings']:,} tokens"
            )

            if preview_info["should_compress"]:
                lines.append("")
                lines.append("**建议**: 当前上下文接近限制，建议使用 `compress` 工具进行压缩。")

        return "\n".join(lines)
