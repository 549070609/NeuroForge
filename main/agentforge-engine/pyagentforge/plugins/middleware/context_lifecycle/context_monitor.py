"""
上下文监控器

使用 tiktoken 进行精确的 token 计数和监控
"""

import logging
from typing import TYPE_CHECKING, Any, Protocol

from pyagentforge.config.settings import get_settings
from pyagentforge.plugins.middleware.context_lifecycle.context_usage import ContextUsage

if TYPE_CHECKING:
    from pyagentforge.kernel.message import Message


class SupportsModelName(Protocol):
    model: str


logger = logging.getLogger(__name__)

_encoders: dict[str, Any] = {}


def get_encoder(model: str):
    """获取 tiktoken 编码器。"""
    try:
        import tiktoken

        if "gpt-4" in model.lower() or "gpt-3.5" in model.lower():
            encoding_name = "cl100k_base"
        else:
            encoding_name = "cl100k_base"

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
    """上下文监控器。"""

    def __init__(
        self,
        provider: "SupportsModelName | None" = None,
        max_context_tokens: int | None = None,
    ):
        self.provider = provider
        settings = get_settings()
        self.max_context_tokens = max_context_tokens or settings.max_context_tokens
        self._model = provider.model if provider else "gpt-4"
        self._encoder = None

    @property
    def encoder(self):
        if self._encoder is None:
            self._encoder = get_encoder(self._model)
        return self._encoder

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self.encoder is not None:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.debug(f"tiktoken encoding failed: {e}, using estimation")
        return len(text) // 4

    def count_message_tokens(self, message: "Message") -> int:
        from pyagentforge.kernel.message import TextBlock, ToolUseBlock

        total = 0
        total += 4

        if isinstance(message.content, str):
            total += self.count_tokens(message.content)
        elif isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, TextBlock):
                    total += self.count_tokens(block.text)
                elif isinstance(block, ToolUseBlock):
                    total += self.count_tokens(block.name)
                    total += self.count_tokens(str(block.input))
                    total += 10
                else:
                    total += self.count_tokens(str(block))

        total += 2
        return total

    def count_messages_tokens(self, messages: list["Message"]) -> int:
        return sum(self.count_message_tokens(message) for message in messages)

    def calculate_usage(self, messages: list["Message"], current_turn_tokens: int = 0) -> ContextUsage:
        total_tokens = self.count_messages_tokens(messages) + current_turn_tokens
        return ContextUsage(
            total_tokens=total_tokens,
            max_tokens=self.max_context_tokens,
            message_count=len(messages),
        )

    def should_compact(self, messages: list["Message"], threshold: float = 0.8) -> bool:
        """判断当前上下文是否应触发压缩。"""
        usage = self.calculate_usage(messages)
        return (usage.total_tokens / usage.max_tokens) >= threshold if usage.max_tokens > 0 else False

    def get_compaction_recommendation(self, messages: list["Message"]) -> dict[str, Any]:
        """给出压缩建议，兼容旧测试和 plugin 调用。"""
        usage = self.calculate_usage(messages)
        usage_ratio = (usage.total_tokens / usage.max_tokens) if usage.max_tokens > 0 else 0.0
        settings = get_settings()
        threshold = getattr(settings, "compaction_threshold", 0.8)

        if usage_ratio >= 0.95:
            urgency = "critical"
        elif usage_ratio >= threshold:
            urgency = "high"
        elif usage_ratio >= max(0.6, threshold - 0.1):
            urgency = "medium"
        else:
            urgency = "low"

        needs_compaction = usage_ratio >= threshold
        if usage_ratio >= 0.95:
            strategy = "summarize"
        elif usage_ratio >= threshold:
            strategy = "hybrid"
        else:
            strategy = "truncate"

        reserve_tokens = getattr(settings, "compaction_reserve_tokens", 8000)
        tokens_to_free = max(0, usage.total_tokens - max(0, usage.max_tokens - reserve_tokens))

        if needs_compaction:
            message = (
                f"Context usage is {usage.usage_percentage:.1f}%, compaction recommended."
            )
        else:
            message = (
                f"Context usage is {usage.usage_percentage:.1f}%, compaction not needed yet."
            )

        return {
            "needs_compaction": needs_compaction,
            "urgency": urgency,
            "suggested_strategy": strategy,
            "tokens_to_free": tokens_to_free,
            "message": message,
        }
