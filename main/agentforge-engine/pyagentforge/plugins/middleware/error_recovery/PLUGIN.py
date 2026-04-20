"""
Error Recovery Plugin

Provides automatic retry and recovery from API errors.
"""

from typing import TYPE_CHECKING, Any

from pyagentforge.config.settings import get_settings
from pyagentforge.plugins.middleware.error_recovery.error_recovery import (
    ErrorClassifier,
    ErrorType,
    RetryManager,
    RetryPolicy,
    RetryResult,
)
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.plugins.middleware.error_recovery.anthropic_recovery import (
    TokenLimitRecovery,
)
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.kernel.context import ContextManager

logger = get_logger(__name__)


class ErrorRecoveryPlugin(Plugin):
    """
    Error Recovery Plugin

    Features:
    - Automatic retry with exponential backoff
    - Rate limit handling
    - Timeout recovery
    - Token limit recovery
    - Configurable retry policies
    """

    metadata = PluginMetadata(
        id="middleware.error_recovery",
        name="Error Recovery",
        version="1.0.0",
        type=PluginType.MIDDLEWARE,
        description="Automatic retry and recovery from API errors",
        author="PyAgentForge",
        provides=["error_recovery", "retry_manager"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._retry_manager: RetryManager | None = None
        self._token_limit_recovery: TokenLimitRecovery | None = None
        self._classifier: ErrorClassifier | None = None
        self._enabled: bool = True
        self._provider: str = ""

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config
        config = self.context.config or {}
        self._enabled = config.get("enabled", True)

        settings = get_settings()

        # Create retry policy
        policy = RetryPolicy(
            max_retries=config.get("max_retries", 3),
            initial_delay=config.get("initial_delay", 1.0),
            max_delay=config.get("max_delay", 60.0),
            backoff_factor=config.get("backoff_factor", 2.0),
            jitter=config.get("jitter", True),
        )

        # Create retry manager
        self._retry_manager = RetryManager(policy=policy)

        # Create token-limit recovery handler
        self._token_limit_recovery = TokenLimitRecovery(
            max_context_tokens=settings.max_context_tokens
        )

        # Create error classifier
        self._classifier = ErrorClassifier()

        # Register hooks
        self.context.hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            self,
            self._on_before_llm_call,
        )
        self.context.hook_registry.register(
            HookType.ON_AFTER_LLM_CALL,
            self,
            self._on_after_llm_call,
        )

        self.context.logger.info(
            "Error recovery plugin activated",
            extra_data={
                "enabled": self._enabled,
                "max_retries": policy.max_retries,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    async def _on_before_llm_call(
        self,
        context: "ContextManager",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Before LLM call - reset recovery state

        Args:
            context: Context manager

        Returns:
            None
        """
        if not self._enabled:
            return None

        # Reset recovery attempts
        if self._token_limit_recovery:
            self._token_limit_recovery.reset_recovery_attempts()

        return None

    async def _on_after_llm_call(
        self,
        response: Any,
        context: "ContextManager",
        error: Exception | None = None,
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: After LLM call - handle errors if any

        Args:
            response: LLM response (may be None if error)
            context: Context manager
            error: Exception if one occurred

        Returns:
            Recovery info if recovery was attempted
        """
        if not self._enabled or error is None:
            return None

        # Classify error
        error_type = self._classifier.classify(error)

        self.context.logger.warning(
            f"LLM call error: {error_type.value}",
            extra_data={
                "error_type": error_type.value,
                "error": str(error),
            },
        )

        # Handle token limit errors
        if error_type == ErrorType.TOKEN_LIMIT and self._token_limit_recovery:
            recovered, message, strategy = (
                self._token_limit_recovery.recover_from_token_limit(context, error)
            )

            if recovered:
                self.context.logger.info(
                    "Recovered from token limit error",
                    extra_data={
                        "strategy": strategy.value if strategy else None,
                        "message": message,
                    },
                )
                return {
                    "recovered": True,
                    "error_type": error_type.value,
                    "recovery_strategy": strategy.value if strategy else None,
                    "message": message,
                }

        return {
            "recovered": False,
            "error_type": error_type.value,
            "error": str(error),
        }

    def execute_with_retry(
        self,
        func: Any,
        *args,
        **kwargs,
    ) -> RetryResult:
        """
        Execute a function with retry logic

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult
        """
        if self._retry_manager is None:
            raise RuntimeError("Retry manager not initialized")

        return self._retry_manager.execute_with_retry(func, *args, **kwargs)

    async def execute_with_retry_async(
        self,
        func: Any,
        *args,
        **kwargs,
    ) -> RetryResult:
        """
        Execute an async function with retry logic

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult
        """
        if self._retry_manager is None:
            raise RuntimeError("Retry manager not initialized")

        return await self._retry_manager.execute_with_retry(func, *args, **kwargs)

    def handle_error(
        self,
        error: Exception,
        context: "ContextManager",
    ) -> dict[str, Any]:
        """
        Handle an error manually

        Args:
            error: Exception to handle
            context: Context manager

        Returns:
            Handling result
        """
        if self._classifier is None:
            return {"error": "Classifier not initialized"}

        error_type = self._classifier.classify(error)

        result = {
            "error_type": error_type.value,
            "handled": False,
        }

        # Token limit recovery
        if error_type == ErrorType.TOKEN_LIMIT and self._token_limit_recovery:
            recovered, message, strategy = (
                self._token_limit_recovery.recover_from_token_limit(context, error)
            )
            result["handled"] = recovered
            result["recovery_message"] = message
            result["recovery_strategy"] = strategy.value if strategy else None

        return result

    def get_retry_manager(self) -> RetryManager | None:
        """Get the retry manager"""
        return self._retry_manager

    def get_classifier(self) -> ErrorClassifier | None:
        """Get the error classifier"""
        return self._classifier
