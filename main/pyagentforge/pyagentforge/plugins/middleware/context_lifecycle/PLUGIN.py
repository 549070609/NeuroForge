"""
Context Lifecycle Plugin

Monitors context usage and triggers preemptive compaction to prevent token limit errors.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pyagentforge.config.settings import get_settings
from pyagentforge.core.context_monitor import ContextMonitor
from pyagentforge.core.context_usage import CompactionStrategyType, ContextUsage
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.core.context import ContextManager
    from pyagentforge.providers.base import BaseProvider

logger = get_logger(__name__)


@dataclass
class ContextLifecycleConfig:
    """Context lifecycle configuration"""

    enabled: bool = True
    compaction_threshold: float = 0.8  # 触发压缩的阈值
    critical_threshold: float = 0.95  # 危险阈值
    default_strategy: CompactionStrategyType = CompactionStrategyType.HYBRID
    reserve_tokens: int = 8000
    monitor_interval: int = 1  # 每 N 次 LLM 调用检查一次


class ContextLifecyclePlugin(Plugin):
    """
    Context Lifecycle Management Plugin

    Features:
    - Monitor context usage with precise token counting
    - Trigger preemptive compaction before reaching limits
    - Support multiple compaction strategies
    - Provide usage reports and recommendations
    """

    metadata = PluginMetadata(
        id="middleware.context_lifecycle",
        name="Context Lifecycle Manager",
        version="1.0.0",
        type=PluginType.MIDDLEWARE,
        description="Monitors context usage and triggers preemptive compaction",
        author="PyAgentForge",
        provides=["context_monitor", "context_lifecycle"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._config = ContextLifecycleConfig()
        self._monitor: ContextMonitor | None = None
        self._call_count = 0
        self._last_usage: ContextUsage | None = None
        self._compaction_callback: Any = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config from context
        config = self.context.config or {}
        self._config = ContextLifecycleConfig(
            enabled=config.get("enabled", True),
            compaction_threshold=config.get("compaction_threshold", 0.8),
            critical_threshold=config.get("critical_threshold", 0.95),
            default_strategy=CompactionStrategyType(
                config.get("default_strategy", "hybrid")
            ),
            reserve_tokens=config.get("reserve_tokens", 8000),
            monitor_interval=config.get("monitor_interval", 1),
        )

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
            "Context lifecycle plugin activated",
            extra_data={
                "compaction_threshold": self._config.compaction_threshold,
                "critical_threshold": self._config.critical_threshold,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    def initialize_monitor(self, provider: "BaseProvider") -> None:
        """
        Initialize the context monitor with provider

        Args:
            provider: LLM provider for model info
        """
        settings = get_settings()
        self._monitor = ContextMonitor(
            provider=provider,
            max_context_tokens=settings.max_context_tokens,
        )
        self.context.logger.info(
            "Context monitor initialized",
            extra_data={"model": provider.model},
        )

    def set_compaction_callback(self, callback: Any) -> None:
        """
        Set the callback function for compaction

        Args:
            callback: Async function that performs compaction and returns CompactionResult
        """
        self._compaction_callback = callback

    async def _on_before_llm_call(
        self,
        context: "ContextManager",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Before LLM call - check context usage and trigger compaction if needed

        Args:
            context: Context manager

        Returns:
            Optional modification to apply
        """
        if not self._config.enabled:
            return None

        self._call_count += 1

        # Skip if not at monitoring interval
        if self._call_count % self._config.monitor_interval != 0:
            return None

        # Ensure monitor is initialized
        if self._monitor is None:
            return None

        # Calculate current usage
        usage = self._monitor.calculate_usage(
            context.messages,
            context.get_loaded_skills(),
        )
        self._last_usage = usage

        # Check if compaction is needed
        if usage.is_high_usage:
            recommendation = self._monitor.get_compaction_recommendation(
                context.messages
            )

            self.context.logger.warning(
                "Context usage high, compaction recommended",
                extra_data={
                    "usage_percentage": usage.usage_percentage,
                    "urgency": recommendation["urgency"],
                    "message": recommendation["message"],
                },
            )

            # If we have a compaction callback and urgency is high, trigger it
            if (
                self._compaction_callback
                and recommendation["urgency"] in ("high", "critical")
            ):
                self.context.logger.info(
                    "Triggering preemptive compaction",
                    extra_data={
                        "strategy": recommendation["suggested_strategy"],
                        "tokens_to_free": recommendation["tokens_to_free"],
                    },
                )

                try:
                    await self._compaction_callback(
                        strategy=recommendation["suggested_strategy"],
                        target_tokens=recommendation["tokens_to_free"],
                    )
                except Exception as e:
                    self.context.logger.error(
                        f"Compaction failed: {e}",
                        extra_data={"error": str(e)},
                    )

        # Return usage info
        return {
            "context_usage": usage.to_dict(),
            "compaction_recommendation": self._monitor.get_compaction_recommendation(
                context.messages
            ),
        }

    async def _on_after_llm_call(
        self,
        response: Any,
        context: "ContextManager",
        **kwargs,
    ) -> None:
        """
        Hook: After LLM call - update usage stats

        Args:
            response: LLM response
            context: Context manager
        """
        if not self._config.enabled or self._monitor is None:
            return

        # Update usage stats
        usage = self._monitor.calculate_usage(
            context.messages,
            context.get_loaded_skills(),
        )
        self._last_usage = usage

        # Log usage if high
        if usage.is_high_usage:
            self.context.logger.warning(
                "Context usage after LLM call",
                extra_data={
                    "usage_percentage": f"{usage.usage_percentage:.1f}%",
                    "available_tokens": usage.available_tokens,
                },
            )

    def get_current_usage(self) -> ContextUsage | None:
        """Get current context usage"""
        return self._last_usage

    def get_usage_report(self) -> str:
        """Get formatted usage report"""
        if self._last_usage is None:
            return "No usage data available"
        return self._last_usage.format_report()

    def get_monitor(self) -> ContextMonitor | None:
        """Get the context monitor instance"""
        return self._monitor
