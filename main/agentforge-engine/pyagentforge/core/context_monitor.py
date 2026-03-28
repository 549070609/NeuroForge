"""
上下文监控器

使用 tiktoken 进行精确的 token 计数和监控
"""

import logging
from typing import TYPE_CHECKING, Any, Protocol

from pyagentforge.config.settings import get_settings
from pyagentforge.core.context_usage import ContextUsage

if TYPE_CHECKING:
    from pyagentforge.core.message import Message


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
        from pyagentforge.core.message import TextBlock, ToolUseBlock

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
        used_tokens = self.count_messages_tokens(messages) + current_turn_tokens
        usage_ratio = used_tokens / self.max_context_tokens if self.max_context_tokens > 0 else 0.0
        remaining_tokens = max(0, self.max_context_tokens - used_tokens)

        settings = get_settings()
        warning_threshold = settings.context_warning_threshold
        critical_threshold = settings.context_critical_threshold

        is_warning = usage_ratio >= warning_threshold
        is_critical = usage_ratio >= critical_threshold

        return ContextUsage(
            used_tokens=used_tokens,
            max_tokens=self.max_context_tokens,
            usage_ratio=usage_ratio,
            remaining_tokens=remaining_tokens,
            is_warning=is_warning,
            is_critical=is_critical,
        )
