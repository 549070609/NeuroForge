"""
Token Limit Error Recovery

Handles generic token-limit style errors and context overflow recovery.
"""

from typing import TYPE_CHECKING, Any

from pyagentforge.core.error_recovery import (
    ErrorType,
    RecoveryStrategy,
    RecoveryNeededError,
)
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.core.context import ContextManager

logger = get_logger(__name__)


class TokenLimitRecovery:
    """
    Token Limit Error Recovery

    Handles:
    - Token limit errors (context_length_exceeded)
    - Overloaded errors
    - Rate limiting
    """

    # Recovery strategies in order of preference
    TOKEN_LIMIT_STRATEGIES = [
        RecoveryStrategy.REMOVE_OLD_TOOL_RESULTS,
        RecoveryStrategy.TRUNCATE_MESSAGES,
        RecoveryStrategy.EMERGENCY_COMPACT,
        RecoveryStrategy.REDUCE_OUTPUT_TOKENS,
    ]

    def __init__(self, max_context_tokens: int = 200000):
        """
        Initialize token limit recovery

        Args:
            max_context_tokens: Maximum context tokens for the model
        """
        self.max_context_tokens = max_context_tokens
        self._recovery_attempts = 0
        self._max_recovery_attempts = 3

    def is_token_limit_error(self, error: Exception) -> bool:
        """Check if error is a token limit error"""
        error_str = str(error).lower()

        # Generic token-limit error patterns
        patterns = [
            "context_length_exceeded",
            "prompt is too long",
            "max_tokens",
            "this request would exceed",
            "token limit",
        ]

        return any(p in error_str for p in patterns)

    def recover_from_token_limit(
        self,
        context: "ContextManager",
        error: Exception,
    ) -> tuple[bool, str, RecoveryStrategy | None]:
        """
        Attempt to recover from token limit error

        Args:
            context: Context manager
            error: The original error

        Returns:
            (recovered, message, strategy_used)
        """
        if self._recovery_attempts >= self._max_recovery_attempts:
            return False, "Max recovery attempts exceeded", None

        self._recovery_attempts += 1

        # Try strategies in order
        for strategy in self.TOKEN_LIMIT_STRATEGIES:
            try:
                if strategy == RecoveryStrategy.REMOVE_OLD_TOOL_RESULTS:
                    success = self._remove_old_tool_results(context)
                    if success:
                        return (
                            True,
                            "Removed old tool results to free up context",
                            strategy,
                        )

                elif strategy == RecoveryStrategy.TRUNCATE_MESSAGES:
                    success = self._truncate_messages(context)
                    if success:
                        return True, "Truncated message history", strategy

                elif strategy == RecoveryStrategy.EMERGENCY_COMPACT:
                    success = self._emergency_compact(context)
                    if success:
                        return True, "Performed emergency compaction", strategy

                elif strategy == RecoveryStrategy.REDUCE_OUTPUT_TOKENS:
                    # This is handled by reducing max_tokens in next call
                    return True, "Will reduce output tokens", strategy

            except Exception as e:
                logger.warning(
                    f"Recovery strategy {strategy.value} failed: {e}",
                    extra_data={"strategy": strategy.value, "error": str(e)},
                )
                continue

        return False, "All recovery strategies failed", None

    def _remove_old_tool_results(self, context: "ContextManager") -> bool:
        """
        Remove old tool results from context

        Returns:
            True if any results were removed
        """
        from pyagentforge.core.message import Message

        messages = context.messages
        removed_count = 0

        # Find and remove old tool results (keep last 50%)
        new_messages = []
        tool_result_count = sum(1 for m in messages if m.role == "tool")
        keep_count = tool_result_count // 2
        current_tool_count = 0

        # Iterate in reverse to keep recent tool results
        for message in reversed(messages):
            if message.role == "tool":
                current_tool_count += 1
                if current_tool_count <= keep_count:
                    new_messages.insert(0, message)
                else:
                    removed_count += 1
            else:
                new_messages.insert(0, message)

        if removed_count > 0:
            context.messages = new_messages
            logger.info(
                "Removed old tool results",
                extra_data={"removed_count": removed_count},
            )
            return True

        return False

    def _truncate_messages(self, context: "ContextManager") -> bool:
        """
        Truncate message history

        Returns:
            True if messages were truncated
        """
        messages = context.messages
        original_count = len(messages)

        if original_count <= 10:
            return False

        # Keep first message (usually system context) and last 50%
        keep_count = len(messages) // 2
        new_messages = [messages[0]] + messages[-keep_count:]

        context.messages = new_messages
        removed = original_count - len(new_messages)

        logger.info(
            "Truncated messages",
            extra_data={"removed": removed, "remaining": len(new_messages)},
        )

        return removed > 0

    def _emergency_compact(self, context: "ContextManager") -> bool:
        """
        Emergency compaction - remove everything except essential messages

        Returns:
            True if compaction occurred
        """
        messages = context.messages
        original_count = len(messages)

        if original_count <= 5:
            return False

        # Keep only last 5 messages
        new_messages = messages[-5:]
        context.messages = new_messages

        logger.warning(
            "Emergency compaction performed",
            extra_data={"removed": original_count - 5, "remaining": 5},
        )

        return True

    def reset_recovery_attempts(self) -> None:
        """Reset recovery attempt counter"""
        self._recovery_attempts = 0

    def get_recovery_stats(self) -> dict[str, Any]:
        """Get recovery statistics"""
        return {
            "total_recovery_attempts": self._recovery_attempts,
            "max_recovery_attempts": self._max_recovery_attempts,
            "max_context_tokens": self.max_context_tokens,
        }


LegacyTokenLimitRecovery = TokenLimitRecovery
