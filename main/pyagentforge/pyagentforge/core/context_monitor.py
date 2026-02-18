"""
上下文监控器

使用 tiktoken 进行精确的 token 计数和监控
"""

import logging
from typing import TYPE_CHECKING, Any

from pyagentforge.config.settings import get_settings
from pyagentforge.core.context_usage import ContextUsage

if TYPE_CHECKING:
    from pyagentforge.core.message import Message
    from pyagentforge.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Token 编码缓存
_encoders: dict[str, Any] = {}


def get_encoder(model: str):
    """
    获取 tiktoken 编码器

    Args:
        model: 模型名称

    Returns:
        tiktoken 编码器
    """
    try:
        import tiktoken

        # 根据模型选择编码器
        if "gpt-4" in model.lower() or "gpt-3.5" in model.lower():
            encoding_name = "cl100k_base"
        elif "claude" in model.lower():
            encoding_name = "cl100k_base"  # Claude 使用类似的编码
        else:
            encoding_name = "cl100k_base"  # 默认使用 cl100k

        if encoding_name not in _encoders:
            _encoders[encoding_name] = tiktoken.get_encoding(encoding_name)

        return _encoders[encoding_name]
    except ImportError:
        logger.warning("tiktoken not installed, using estimation fallback")
        return None
    except Exception as e:
        logger.warning(f"Failed to load tiktoken encoder: {e}, using estimation fallback")
        return None


class ContextMonitor:
    """
    上下文监控器

    负责监控上下文使用情况，计算 token 数量
    """

    def __init__(
        self,
        provider: "BaseProvider | None" = None,
        max_context_tokens: int | None = None,
    ):
        """
        初始化上下文监控器

        Args:
            provider: LLM 提供商（用于获取模型信息）
            max_context_tokens: 最大上下文 tokens
        """
        self.provider = provider
        settings = get_settings()
        self.max_context_tokens = max_context_tokens or settings.max_context_tokens
        self._model = provider.model if provider else "gpt-4"
        self._encoder = None

    @property
    def encoder(self):
        """懒加载编码器"""
        if self._encoder is None:
            self._encoder = get_encoder(self._model)
        return self._encoder

    def count_tokens(self, text: str) -> int:
        """
        计算文本的 token 数量

        Args:
            text: 输入文本

        Returns:
            token 数量
        """
        if not text:
            return 0

        # 使用 tiktoken 精确计数
        if self.encoder is not None:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.debug(f"tiktoken encoding failed: {e}, using estimation")

        # 回退到启发式估算
        # 中文字符约 2 tokens，英文单词约 1 token
        # 粗略估算：字符数 / 4
        return len(text) // 4

    def count_message_tokens(self, message: "Message") -> int:
        """
        计算单条消息的 token 数量

        Args:
            message: 消息对象

        Returns:
            token 数量
        """
        from pyagentforge.core.message import TextBlock, ToolUseBlock

        total = 0

        # 角色开销
        total += 4  # role, content 等字段名

        if isinstance(message.content, str):
            total += self.count_tokens(message.content)
        elif isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, TextBlock):
                    total += self.count_tokens(block.text)
                elif isinstance(block, ToolUseBlock):
                    # 工具调用包含名称和参数
                    total += self.count_tokens(block.name)
                    total += self.count_tokens(str(block.input))
                    total += 10  # 结构开销
        elif isinstance(message.content, dict):
            # 工具结果格式
            if "content" in message.content:
                total += self.count_tokens(str(message.content["content"]))
            total += 10  # 结构开销

        return total

    def calculate_usage(
        self,
        messages: list["Message"],
        loaded_skills: set[str] | None = None,
    ) -> ContextUsage:
        """
        计算上下文使用情况

        Args:
            messages: 消息列表
            loaded_skills: 已加载的技能

        Returns:
            ContextUsage 对象
        """
        total_tokens = 0
        user_tokens = 0
        assistant_tokens = 0
        tool_tokens = 0

        for message in messages:
            msg_tokens = self.count_message_tokens(message)
            total_tokens += msg_tokens

            # 分类统计
            if message.role == "user":
                user_tokens += msg_tokens
            elif message.role == "assistant":
                assistant_tokens += msg_tokens
            elif message.role == "tool":
                tool_tokens += msg_tokens

        return ContextUsage(
            total_tokens=total_tokens,
            max_tokens=self.max_context_tokens,
            message_count=len(messages),
            loaded_skills=len(loaded_skills) if loaded_skills else 0,
            user_messages_tokens=user_tokens,
            assistant_messages_tokens=assistant_tokens,
            tool_results_tokens=tool_tokens,
        )

    def should_compact(
        self,
        messages: list["Message"],
        threshold: float = 0.8,
    ) -> bool:
        """
        判断是否需要压缩

        Args:
            messages: 消息列表
            threshold: 压缩阈值

        Returns:
            是否需要压缩
        """
        usage = self.calculate_usage(messages)
        return usage.usage_percentage >= threshold * 100

    def get_available_capacity(
        self,
        messages: list["Message"],
        reserve: int = 8000,
    ) -> int:
        """
        获取可用上下文容量

        Args:
            messages: 消息列表
            reserve: 预留 tokens

        Returns:
            可用 tokens
        """
        usage = self.calculate_usage(messages)
        return max(0, usage.available_tokens - reserve)

    def estimate_remaining_iterations(
        self,
        messages: list["Message"],
        avg_iteration_tokens: int = 2000,
    ) -> int:
        """
        估算剩余可执行的迭代次数

        Args:
            messages: 消息列表
            avg_iteration_tokens: 平均每次迭代消耗的 tokens

        Returns:
            估算的剩余迭代次数
        """
        available = self.get_available_capacity(messages)
        return available // max(1, avg_iteration_tokens)

    def get_compaction_recommendation(
        self,
        messages: list["Message"],
    ) -> dict[str, Any]:
        """
        获取压缩建议

        Args:
            messages: 消息列表

        Returns:
            压缩建议
        """
        usage = self.calculate_usage(messages)

        recommendation = {
            "needs_compaction": usage.is_high_usage,
            "urgency": "low",
            "suggested_strategy": "summarize",
            "tokens_to_free": 0,
            "message": "",
        }

        if usage.is_critical_usage:
            recommendation["urgency"] = "critical"
            recommendation["suggested_strategy"] = "truncate"
            recommendation["tokens_to_free"] = int(usage.total_tokens * 0.4)
            recommendation["message"] = (
                f"Critical context usage ({usage.usage_percentage:.1f}%). "
                f"Immediate compaction required."
            )
        elif usage.is_high_usage:
            recommendation["urgency"] = "high"
            recommendation["suggested_strategy"] = "hybrid"
            recommendation["tokens_to_free"] = int(usage.total_tokens * 0.25)
            recommendation["message"] = (
                f"High context usage ({usage.usage_percentage:.1f}%). "
                f"Compaction recommended soon."
            )
        elif usage.usage_percentage >= 60:
            recommendation["urgency"] = "medium"
            recommendation["message"] = (
                f"Moderate context usage ({usage.usage_percentage:.1f}%). "
                f"Consider compaction."
            )
        else:
            recommendation["message"] = (
                f"Context usage is healthy ({usage.usage_percentage:.1f}%)."
            )

        return recommendation
