"""
压缩引擎

执行对话历史压缩，与长记忆联动
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import logging

from .budget_manager import TokenBudgetManager
from .summary_generator import SummaryGenerator, SummaryStrategy

logger = logging.getLogger(__name__)


@dataclass
class CompressResult:
    """压缩结果"""

    compressed_messages: list[dict[str, Any]]
    original_count: int
    compressed_count: int
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    summary_stored: bool
    summary_id: Optional[str] = None


class CompressEngine:
    """
    压缩引擎

    支持:
    - 智能分割消息
    - 多策略摘要生成
    - 与长记忆联动
    - 自动压缩触发
    """

    def __init__(
        self,
        budget_manager: TokenBudgetManager,
        summary_generator: SummaryGenerator,
        long_memory_plugin: Optional[Any] = None,
        keep_recent: int = 20,
    ):
        """
        初始化压缩引擎

        Args:
            budget_manager: 预算管理器
            summary_generator: 摘要生成器
            long_memory_plugin: 长记忆插件实例
            keep_recent: 保留的最近消息数
        """
        self.budget_manager = budget_manager
        self.summary_generator = summary_generator
        self.long_memory = long_memory_plugin
        self.keep_recent = keep_recent

    async def compress(
        self,
        messages: list[dict[str, Any]],
        force: bool = False,
        store_to_memory: bool = True,
        strategy: Optional[SummaryStrategy] = None,
    ) -> CompressResult:
        """
        执行压缩

        Args:
            messages: 消息列表
            force: 强制压缩 (忽略阈值)
            store_to_memory: 是否存储摘要到长记忆
            strategy: 摘要策略

        Returns:
            压缩结果
        """
        # 检查是否需要压缩
        if not force and not self.budget_manager.should_compress(messages):
            budget = self.budget_manager.calculate(messages)
            return CompressResult(
                compressed_messages=messages,
                original_count=len(messages),
                compressed_count=len(messages),
                original_tokens=budget.used_tokens,
                compressed_tokens=budget.used_tokens,
                compression_ratio=1.0,
                summary_stored=False,
            )

        # 获取原始统计
        original_budget = self.budget_manager.calculate(messages)
        original_count = len(messages)

        # 分割消息
        to_compress, to_keep = self._split_messages(messages)

        if not to_compress:
            # 没有需要压缩的内容
            return CompressResult(
                compressed_messages=messages,
                original_count=original_count,
                compressed_count=original_count,
                original_tokens=original_budget.used_tokens,
                compressed_tokens=original_budget.used_tokens,
                compression_ratio=1.0,
                summary_stored=False,
            )

        # 生成摘要
        context = self._build_context(messages)
        summary_result = await self.summary_generator.generate(
            messages=to_compress,
            strategy=strategy,
            context=context,
        )

        # 构建摘要消息
        summary_message = self._build_summary_message(summary_result.content)

        # 组合压缩后的消息
        compressed_messages = [summary_message] + to_keep

        # 计算压缩后的统计
        compressed_budget = self.budget_manager.calculate(compressed_messages)

        # 存储到长记忆
        summary_id = None
        summary_stored = False

        if store_to_memory and self.long_memory:
            try:
                summary_id = await self._store_to_long_memory(
                    summary=summary_result.content,
                    original_messages=to_compress,
                    key_points=summary_result.key_points,
                )
                summary_stored = True
            except Exception as e:
                logger.error(f"Failed to store summary to long memory: {e}")

        result = CompressResult(
            compressed_messages=compressed_messages,
            original_count=original_count,
            compressed_count=len(compressed_messages),
            original_tokens=original_budget.used_tokens,
            compressed_tokens=compressed_budget.used_tokens,
            compression_ratio=compressed_budget.used_tokens / original_budget.used_tokens
            if original_budget.used_tokens > 0
            else 0,
            summary_stored=summary_stored,
            summary_id=summary_id,
        )

        logger.info(
            "Compression completed",
            extra_data={
                "original_count": original_count,
                "compressed_count": len(compressed_messages),
                "compression_ratio": f"{result.compression_ratio:.2%}",
                "summary_stored": summary_stored,
            },
        )

        return result

    def _split_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        分割消息为待压缩和保留两部分

        Args:
            messages: 消息列表

        Returns:
            (待压缩的消息, 保留的消息)
        """
        if len(messages) <= self.keep_recent:
            return [], messages

        # 保留系统消息和最近的消息
        system_messages = []
        other_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        # 计算分割点
        split_point = len(other_messages) - self.keep_recent
        if split_point <= 0:
            return [], messages

        to_compress = other_messages[:split_point]
        to_keep = system_messages + other_messages[split_point:]

        return to_compress, to_keep

    def _build_context(self, messages: list[dict[str, Any]]) -> str:
        """构建上下文信息"""
        # 提取第一条用户消息作为上下文
        for msg in messages:
            if msg.get("role") == "user":
                content = self._get_text_content(msg)
                if content:
                    # 取前 200 字符作为上下文
                    return content[:200] + ("..." if len(content) > 200 else "")

        return ""

    def _build_summary_message(self, summary: str) -> dict[str, Any]:
        """
        构建摘要消息

        Args:
            summary: 摘要内容

        Returns:
            摘要消息
        """
        now = datetime.now(timezone.utc).isoformat()
        content = f"""## 历史对话摘要

以下是对话历史的压缩摘要:

{summary}

---
*摘要生成时间: {now}*
*可以使用 `memory_recall` 工具查询更多历史信息*
"""

        return {
            "role": "user",
            "content": content,
        }

    async def _store_to_long_memory(
        self,
        summary: str,
        original_messages: list[dict[str, Any]],
        key_points: list[str],
    ) -> str:
        """
        存储摘要到长记忆

        Args:
            summary: 摘要内容
            original_messages: 原始消息
            key_points: 关键点

        Returns:
            记忆 ID
        """
        if not self.long_memory:
            raise ValueError("Long memory plugin not available")

        # 构建元数据
        metadata = {
            "message_count": len(original_messages),
            "key_points": key_points,
            "compression_time": datetime.now(timezone.utc).isoformat(),
        }

        # 存储为摘要记忆
        memory_id = await self.long_memory.store_summary(
            summary=summary,
            original_context=self._build_context(original_messages),
            importance=0.8,  # 摘要通常很重要
        )

        logger.debug(
            "Summary stored to long memory",
            extra_data={"memory_id": memory_id},
        )

        return memory_id

    def _get_text_content(self, msg: dict[str, Any]) -> str:
        """获取消息的文本内容"""
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            return "\n".join(texts)
        return ""

    def get_compress_preview(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        获取压缩预览

        Args:
            messages: 消息列表

        Returns:
            预览信息
        """
        budget = self.budget_manager.calculate(messages)
        to_compress, to_keep = self._split_messages(messages)

        return {
            "should_compress": self.budget_manager.should_compress(messages),
            "budget": {
                "used": budget.used_tokens,
                "total": budget.total_tokens,
                "ratio": f"{budget.compression_ratio:.1%}",
            },
            "split": {
                "total_messages": len(messages),
                "to_compress": len(to_compress),
                "to_keep": len(to_keep),
            },
            "estimated_savings": self.budget_manager.estimate_compress_savings(
                len(to_compress)
            ),
        }
