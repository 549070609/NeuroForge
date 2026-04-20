"""
Error Recovery

Retry policies and error recovery mechanisms.
"""

import asyncio
import random
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, TypeVar

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ErrorType(StrEnum):
    """Error type classification"""

    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    OVERLOADED = "overloaded"
    TOKEN_LIMIT = "token_limit"
    CONTEXT_OVERFLOW = "context_overflow"
    AUTH_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


class RetryDecision(StrEnum):
    """Retry decision"""

    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    RECOVER = "recover"  # Apply recovery strategy
    FAIL = "fail"  # Don't retry


@dataclass
class RetryPolicy:
    """Retry policy configuration"""

    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_errors: list[ErrorType] = field(
        default_factory=lambda: [
            ErrorType.RATE_LIMIT,
            ErrorType.TIMEOUT,
            ErrorType.OVERLOADED,
            ErrorType.NETWORK_ERROR,
        ]
    )


@dataclass
class RetryResult:
    """Result of retry operation"""

    success: bool
    attempts: int
    total_delay: float
    last_error: Exception | None = None
    result: Any = None


@dataclass
class ErrorContext:
    """Context for error handling"""

    error: Exception
    error_type: ErrorType
    attempt: int
    total_attempts: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Provider-specific info
    provider: str = ""
    model: str = ""

    # Token info
    tokens_used: int = 0
    tokens_remaining: int = 0


class ErrorClassifier:
    """Classify errors into types"""

    @staticmethod
    def classify(error: Exception) -> ErrorType:
        """
        Classify an exception into an error type

        Args:
            error: Exception to classify

        Returns:
            ErrorType classification
        """
        error_str = str(error).lower()
        type(error).__name__.lower()

        # Rate limit errors
        if any(
            kw in error_str
            for kw in ["rate limit", "429", "too many requests", "rate_limit"]
        ):
            return ErrorType.RATE_LIMIT

        # Timeout errors
        if any(
            kw in error_str
            for kw in ["timeout", "timed out", "deadline exceeded", "timeouterror"]
        ):
            return ErrorType.TIMEOUT

        # Overloaded errors
        if any(
            kw in error_str
            for kw in ["overloaded", "capacity", "temporarily unavailable"]
        ):
            return ErrorType.OVERLOADED

        # Token limit errors (Anthropic specific)
        if any(
            kw in error_str
            for kw in [
                "token limit",
                "context_length_exceeded",
                "max_tokens",
                "too many tokens",
                "prompt is too long",
            ]
        ):
            return ErrorType.TOKEN_LIMIT

        # Context overflow
        if any(kw in error_str for kw in ["context overflow", "context too large"]):
            return ErrorType.CONTEXT_OVERFLOW

        # Auth errors
        if any(
            kw in error_str
            for kw in ["unauthorized", "401", "invalid api key", "authentication"]
        ):
            return ErrorType.AUTH_ERROR

        # Network errors
        if any(
            kw in error_str
            for kw in ["connection", "network", "dns", "socket", "connectionerror"]
        ):
            return ErrorType.NETWORK_ERROR

        return ErrorType.UNKNOWN


class RetryManager:
    """
    Retry Manager

    Manages retry logic with exponential backoff and jitter.
    """

    def __init__(self, policy: RetryPolicy | None = None):
        """
        Initialize retry manager

        Args:
            policy: Retry policy configuration
        """
        self.policy = policy or RetryPolicy()
        self.classifier = ErrorClassifier()

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.policy.initial_delay * (
            self.policy.backoff_factor ** (attempt - 1)
        )

        # Cap at max delay
        delay = min(delay, self.policy.max_delay)

        # Add jitter
        if self.policy.jitter:
            jitter = random.uniform(0, 0.1) * delay
            delay += jitter

        return delay

    def should_retry(
        self,
        error: Exception,
        attempt: int,
    ) -> tuple[RetryDecision, float]:
        """
        Determine if we should retry

        Args:
            error: Exception that occurred
            attempt: Current attempt number

        Returns:
            (decision, delay) tuple
        """
        error_type = self.classifier.classify(error)

        # Check max retries
        if attempt >= self.policy.max_retries:
            return RetryDecision.FAIL, 0

        # Check if retryable
        if error_type in self.policy.retryable_errors:
            delay = self.calculate_delay(attempt)
            return RetryDecision.RETRY_WITH_BACKOFF, delay

        # Token limit errors need recovery
        if error_type == ErrorType.TOKEN_LIMIT:
            return RetryDecision.RECOVER, 0

        # Auth errors shouldn't be retried
        if error_type == ErrorType.AUTH_ERROR:
            return RetryDecision.FAIL, 0

        # Unknown errors - try once more
        if error_type == ErrorType.UNKNOWN and attempt < 2:
            return RetryDecision.RETRY, self.policy.initial_delay

        return RetryDecision.FAIL, 0

    async def execute_with_retry(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> RetryResult:
        """
        Execute function with retry logic

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult with outcome
        """
        attempt = 0
        total_delay = 0.0
        last_error = None

        while attempt < self.policy.max_retries:
            attempt += 1

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                return RetryResult(
                    success=True,
                    attempts=attempt,
                    total_delay=total_delay,
                    result=result,
                )

            except Exception as e:
                last_error = e
                error_type = self.classifier.classify(e)

                logger.warning(
                    f"Attempt {attempt} failed: {error_type.value}",
                    extra_data={
                        "error": str(e),
                        "error_type": error_type.value,
                        "attempt": attempt,
                    },
                )

                # Decide what to do
                decision, delay = self.should_retry(e, attempt)

                if decision == RetryDecision.FAIL:
                    break
                elif decision == RetryDecision.RECOVER:
                    # Signal recovery needed
                    raise RecoveryNeededError(e) from e

                # Wait before retry
                if delay > 0:
                    await asyncio.sleep(delay)
                    total_delay += delay

        return RetryResult(
            success=False,
            attempts=attempt,
            total_delay=total_delay,
            last_error=last_error,
        )


class RecoveryNeededError(Exception):
    """Exception signaling that recovery is needed"""

    def __init__(self, original_error: Exception):
        self.original_error = original_error
        super().__init__(f"Recovery needed for: {original_error}")


class RecoveryStrategy(StrEnum):
    """Recovery strategy for token limit errors"""

    REMOVE_OLD_TOOL_RESULTS = "remove_old_tool_results"
    TRUNCATE_MESSAGES = "truncate_messages"
    EMERGENCY_COMPACT = "emergency_compact"
    REDUCE_OUTPUT_TOKENS = "reduce_output_tokens"


@dataclass
class RecoveryResult:
    """Recovery execution result"""

    success: bool
    strategy: RecoveryStrategy
    messages_removed: int = 0
    tokens_freed: int = 0
    error: str | None = None


class RecoveryExecutor:
    """
    Recovery Strategy Executor

    Executes recovery strategies for token limit and context overflow errors.

    Usage:
        executor = RecoveryExecutor(context_manager, compactor)
        result = await executor.execute(RecoveryStrategy.REMOVE_OLD_TOOL_RESULTS)
        if result.success:
            # Retry the LLM call
    """

    def __init__(
        self,
        context: Any,  # ContextManager
        compactor: Any | None = None,  # Compactor
        settings: Any | None = None,  # Settings
    ):
        """
        Initialize recovery executor

        Args:
            context: ContextManager instance
            compactor: Optional Compactor for emergency compaction
            settings: Optional Settings instance
        """
        self.context = context
        self.compactor = compactor
        self.settings = settings
        self._strategy_handlers: dict[
            RecoveryStrategy,
            Callable[[], Coroutine[Any, Any, RecoveryResult]],
        ] = {
            RecoveryStrategy.REMOVE_OLD_TOOL_RESULTS: self._remove_old_tool_results,
            RecoveryStrategy.TRUNCATE_MESSAGES: self._truncate_messages,
            RecoveryStrategy.EMERGENCY_COMPACT: self._emergency_compact,
            RecoveryStrategy.REDUCE_OUTPUT_TOKENS: self._reduce_output_tokens,
        }

    async def execute(
        self,
        strategy: RecoveryStrategy,
    ) -> RecoveryResult:
        """
        Execute a recovery strategy

        Args:
            strategy: Strategy to execute

        Returns:
            RecoveryResult with outcome
        """
        handler = self._strategy_handlers.get(strategy)
        if handler is None:
            return RecoveryResult(
                success=False,
                strategy=strategy,
                error=f"Unknown strategy: {strategy}",
            )

        try:
            logger.info(
                f"Executing recovery strategy: {strategy.value}",
                extra_data={"strategy": strategy.value},
            )

            result = await handler()

            logger.info(
                f"Recovery strategy completed: {strategy.value}",
                extra_data={
                    "success": result.success,
                    "messages_removed": result.messages_removed,
                },
            )

            return result

        except Exception as e:
            logger.error(
                f"Recovery strategy failed: {strategy.value}",
                extra_data={"error": str(e)},
            )
            return RecoveryResult(
                success=False,
                strategy=strategy,
                error=str(e),
            )

    async def execute_all(self) -> list[RecoveryResult]:
        """
        Execute all recovery strategies in order until one succeeds

        Returns:
            List of results from all attempts
        """
        results = []

        for strategy in [
            RecoveryStrategy.REMOVE_OLD_TOOL_RESULTS,
            RecoveryStrategy.TRUNCATE_MESSAGES,
            RecoveryStrategy.EMERGENCY_COMPACT,
            RecoveryStrategy.REDUCE_OUTPUT_TOKENS,
        ]:
            result = await self.execute(strategy)
            results.append(result)

            if result.success:
                break

        return results

    async def _remove_old_tool_results(self) -> RecoveryResult:
        """
        Remove old tool_result messages from context

        Strategy: Remove the oldest tool_result messages while preserving
        the conversation flow.
        """
        messages = self.context.messages
        removed_count = 0

        # Find and remove old tool_result messages
        # Keep at least the most recent N tool results
        keep_recent = 5
        tool_result_indices = []

        for i, msg in enumerate(messages):
            if msg.role == "user" and self._has_tool_result(msg):
                tool_result_indices.append(i)

        # Remove oldest first, keep recent ones
        to_remove = tool_result_indices[:-keep_recent] if len(tool_result_indices) > keep_recent else []

        # Remove in reverse order to preserve indices
        for idx in reversed(to_remove):
            messages.pop(idx)
            removed_count += 1

        return RecoveryResult(
            success=removed_count > 0,
            strategy=RecoveryStrategy.REMOVE_OLD_TOOL_RESULTS,
            messages_removed=removed_count,
            tokens_freed=removed_count * 500,  # Estimate
        )

    def _has_tool_result(self, message: Any) -> bool:
        """Check if a message contains a tool_result"""
        content = getattr(message, "content", None)
        if content is None:
            return False

        # Check for tool_result block
        if isinstance(content, list):
            for block in content:
                if getattr(block, "type", None) == "tool_result":
                    return True
        return False

    async def _truncate_messages(self) -> RecoveryResult:
        """
        Truncate message history to reduce token count

        Strategy: Keep only the most recent messages, preserving
        system messages and the first user message if possible.
        """
        messages = self.context.messages
        original_count = len(messages)

        # Target: keep 50% of messages
        target_keep = max(10, original_count // 2)

        # Always keep system and first user message
        # Then keep the most recent messages
        if original_count <= target_keep:
            return RecoveryResult(
                success=False,
                strategy=RecoveryStrategy.TRUNCATE_MESSAGES,
                error="Already at minimum message count",
            )

        # Truncate to target
        removed = self.context.truncate(keep_last=target_keep)

        return RecoveryResult(
            success=removed > 0,
            strategy=RecoveryStrategy.TRUNCATE_MESSAGES,
            messages_removed=removed,
            tokens_freed=removed * 300,  # Estimate
        )

    async def _emergency_compact(self) -> RecoveryResult:
        """
        Perform emergency context compaction

        Strategy: Use Compactor to summarize old messages and
        free up token space.
        """
        if self.compactor is None:
            # Try to import and create compactor
            try:
                from pyagentforge.plugins.middleware.compaction.compaction import Compactor

                self.compactor = Compactor()
            except ImportError:
                return RecoveryResult(
                    success=False,
                    strategy=RecoveryStrategy.EMERGENCY_COMPACT,
                    error="Compactor not available",
                )

        try:
            # Perform compaction
            result = await self.compactor.compact(self.context.messages)

            return RecoveryResult(
                success=True,
                strategy=RecoveryStrategy.EMERGENCY_COMPACT,
                messages_removed=result.messages_removed,
                tokens_freed=result.tokens_saved,
            )

        except Exception as e:
            return RecoveryResult(
                success=False,
                strategy=RecoveryStrategy.EMERGENCY_COMPACT,
                error=str(e),
            )

    async def _reduce_output_tokens(self) -> RecoveryResult:
        """
        Reduce max_output_tokens setting

        Strategy: Temporarily reduce the max_tokens for the next
        LLM call to fit within limits.
        """
        if self.settings is None:
            try:
                from pyagentforge.config.settings import get_settings

                self.settings = get_settings()
            except Exception:
                return RecoveryResult(
                    success=False,
                    strategy=RecoveryStrategy.REDUCE_OUTPUT_TOKENS,
                    error="Settings not available",
                )

        original_max_tokens = self.settings.max_tokens
        reduction_factor = 0.5  # Reduce by 50%

        # Calculate new max_tokens
        new_max_tokens = int(original_max_tokens * reduction_factor)
        new_max_tokens = max(1024, new_max_tokens)  # Keep at least 1024

        # Update settings
        self.settings.max_tokens = new_max_tokens

        logger.info(
            f"Reduced max_tokens from {original_max_tokens} to {new_max_tokens}",
            extra_data={
                "original": original_max_tokens,
                "new": new_max_tokens,
            },
        )

        return RecoveryResult(
            success=True,
            strategy=RecoveryStrategy.REDUCE_OUTPUT_TOKENS,
            tokens_freed=original_max_tokens - new_max_tokens,
        )


class RetryManagerWithRecovery(RetryManager):
    """
    Extended RetryManager with automatic recovery support

    Automatically handles RecoveryNeededError by executing recovery
    strategies and retrying.
    """

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        recovery_executor: RecoveryExecutor | None = None,
    ):
        super().__init__(policy)
        self.recovery_executor = recovery_executor

    def set_recovery_executor(self, executor: RecoveryExecutor) -> None:
        """Set the recovery executor"""
        self.recovery_executor = executor

    async def execute_with_retry(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> RetryResult:
        """
        Execute function with retry and recovery logic

        Extends base implementation to handle RecoveryNeededError
        by executing recovery strategies before retrying.
        """
        attempt = 0
        total_delay = 0.0
        last_error = None
        recovery_attempts = 0
        max_recovery_attempts = 3

        while attempt < self.policy.max_retries:
            attempt += 1

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                return RetryResult(
                    success=True,
                    attempts=attempt,
                    total_delay=total_delay,
                    result=result,
                )

            except RecoveryNeededError as e:
                last_error = e.original_error

                logger.warning(
                    f"Recovery needed on attempt {attempt}",
                    extra_data={"error": str(e.original_error)},
                )

                # Execute recovery if executor is available
                if self.recovery_executor and recovery_attempts < max_recovery_attempts:
                    recovery_attempts += 1

                    recovery_result = await self.recovery_executor.execute_all()

                    # Check if any recovery succeeded
                    any_success = any(r.success for r in recovery_result)

                    if any_success:
                        logger.info(
                            "Recovery successful, retrying...",
                            extra_data={"recovery_attempts": recovery_attempts},
                        )
                        # Don't count this as a retry attempt
                        attempt -= 1
                        continue
                    else:
                        logger.error(
                            "All recovery strategies failed",
                            extra_data={"results": [r.strategy.value for r in recovery_result]},
                        )

                # No recovery possible
                break

            except Exception as e:
                last_error = e
                error_type = self.classifier.classify(e)

                logger.warning(
                    f"Attempt {attempt} failed: {error_type.value}",
                    extra_data={
                        "error": str(e),
                        "error_type": error_type.value,
                        "attempt": attempt,
                    },
                )

                # Decide what to do
                decision, delay = self.should_retry(e, attempt)

                if decision == RetryDecision.FAIL:
                    break
                elif decision == RetryDecision.RECOVER:
                    # Signal recovery needed
                    raise RecoveryNeededError(e) from e

                # Wait before retry
                if delay > 0:
                    await asyncio.sleep(delay)
                    total_delay += delay

        return RetryResult(
            success=False,
            attempts=attempt,
            total_delay=total_delay,
            last_error=last_error,
        )
