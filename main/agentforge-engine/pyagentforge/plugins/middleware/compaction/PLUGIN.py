"""
Compaction Plugin

提供上下文压缩功能，支持：
- 简单 LLM 摘要压缩
- Agent 智能压缩
- 动态配置压缩参数
"""

import logging
from typing import Any, Callable

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class CompactionPlugin(Plugin):
    """上下文压缩插件"""

    metadata = PluginMetadata(
        id="middleware.compaction",
        name="Context Compaction",
        version="2.0.0",
        type=PluginType.MIDDLEWARE,
        description="当对话历史过长时，使用 LLM 或 Agent 生成摘要来压缩上下文，支持动态配置",
        author="PyAgentForge",
        provides=["compaction", "compaction.dynamic_config"],
        dependencies=[],
        optional_dependencies=["integration.events"],
        priority=10,  # 较高优先级，在其他中间件之前加载
    )

    def __init__(self):
        super().__init__()
        self._compactor = None
        self._settings = None
        self._dynamic_config = None
        self._strategy = "simple"

    async def on_plugin_load(self, context) -> None:
        """加载插件"""
        await super().on_plugin_load(context)

        # 从配置获取设置
        config = context.config or {}

        from pyagentforge.plugins.middleware.compaction.compaction import (
            CompactionSettings,
            CompactionStrategy,
            DynamicCompactionConfig,
        )

        # 解析压缩策略
        strategy_str = config.get("strategy", "simple")
        try:
            strategy = CompactionStrategy(strategy_str)
        except ValueError:
            strategy = CompactionStrategy.SIMPLE

        self._strategy = strategy.value

        # 创建压缩设置
        self._settings = CompactionSettings(
            enabled=config.get("enabled", True),
            strategy=strategy,
            reserve_tokens=config.get("reserve_tokens", 8000),
            keep_recent_tokens=config.get("keep_recent_tokens", 4000),
            trigger_threshold=config.get("trigger_threshold", 0.8),
            max_context_tokens=config.get("max_context_tokens", 200000),
            agent_summary_max_tokens=config.get("agent_summary_max_tokens", 2000),
            agent_analyze_recent=config.get("agent_analyze_recent", 5),
        )

        # 创建动态配置管理器
        adaptive_enabled = config.get("adaptive", False)
        self._dynamic_config = DynamicCompactionConfig(
            base_settings=self._settings,
            on_threshold_change=self._on_threshold_changed,
        )
        if adaptive_enabled:
            self._dynamic_config.enable_adaptive(True)

        self.context.logger.info(
            f"Compaction settings loaded: strategy={strategy.value}, "
            f"threshold={self._settings.trigger_threshold:.2f}"
        )

    async def on_plugin_activate(self) -> None:
        """激活插件"""
        await super().on_plugin_activate()

        # 创建压缩器
        if self.context.engine and self.context.engine.provider:
            from pyagentforge.plugins.middleware.compaction.compaction import create_compactor

            # 如果使用 Agent 策略，可以传入 agent_engine
            agent_engine = None
            if self._strategy == "agent":
                # 可以选择传入主引擎或创建专用的压缩 Agent
                agent_engine = self.context.engine

            self._compactor = create_compactor(
                provider=self.context.engine.provider,
                settings=self._settings,
                max_context_tokens=self._settings.max_context_tokens,
                agent_engine=agent_engine,
            )

            self.context.logger.info(
                f"Compactor initialized: strategy={self._strategy}"
            )

    def _on_threshold_changed(self, new_threshold: float) -> None:
        """阈值变更回调"""
        if self.context and self.context.logger:
            self.context.logger.info(
                f"Dynamic compaction threshold changed to {new_threshold:.2f}"
            )

    # ==================== 动态配置 API ====================

    def update_threshold(self, threshold: float) -> bool:
        """
        动态更新压缩阈值

        Args:
            threshold: 新的阈值 (0.0 - 1.0)

        Returns:
            是否更新成功
        """
        if not 0.0 <= threshold <= 1.0:
            return False

        if self._dynamic_config:
            self._dynamic_config.update_threshold(threshold)
            # 同步更新压缩器设置
            if self._compactor and hasattr(self._compactor, 'settings'):
                self._compactor.settings.trigger_threshold = threshold
            return True
        return False

    def update_max_context_tokens(self, max_tokens: int) -> bool:
        """
        动态更新最大上下文 tokens

        Args:
            max_tokens: 新的最大 tokens

        Returns:
            是否更新成功
        """
        if max_tokens < 1000:
            return False

        if self._dynamic_config:
            self._dynamic_config.update_max_context_tokens(max_tokens)
            if self._compactor and hasattr(self._compactor, 'max_context_tokens'):
                self._compactor.max_context_tokens = max_tokens
            return True
        return False

    def update_strategy(self, strategy: str) -> bool:
        """
        动态更新压缩策略

        Args:
            strategy: 新的策略 ("simple" 或 "agent")

        Returns:
            是否更新成功
        """
        from pyagentforge.plugins.middleware.compaction.compaction import CompactionStrategy

        try:
            new_strategy = CompactionStrategy(strategy)
        except ValueError:
            return False

        if self._dynamic_config:
            self._dynamic_config.update_strategy(new_strategy)
            self._strategy = new_strategy.value

            # 需要重新创建压缩器
            if self.context and self.context.engine:
                from pyagentforge.plugins.middleware.compaction.compaction import create_compactor

                agent_engine = None
                if new_strategy == CompactionStrategy.AGENT:
                    agent_engine = self.context.engine

                self._compactor = create_compactor(
                    provider=self.context.engine.provider,
                    settings=self._settings,
                    max_context_tokens=self._settings.max_context_tokens,
                    agent_engine=agent_engine,
                )

            return True
        return False

    def enable_adaptive(self, enabled: bool = True) -> None:
        """
        启用/禁用自适应压缩

        自适应压缩会根据历史压缩效果自动调整阈值
        """
        if self._dynamic_config:
            self._dynamic_config.enable_adaptive(enabled)
            self.context.logger.info(
                f"Adaptive compaction {'enabled' if enabled else 'disabled'}"
            )

    def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        if not self._settings:
            return {}

        return {
            "enabled": self._settings.enabled,
            "strategy": self._settings.strategy,
            "trigger_threshold": self._settings.trigger_threshold,
            "max_context_tokens": self._settings.max_context_tokens,
            "reserve_tokens": self._settings.reserve_tokens,
            "keep_recent_tokens": self._settings.keep_recent_tokens,
            "adaptive_enabled": (
                self._dynamic_config._adaptive_enabled
                if self._dynamic_config else False
            ),
        }

    # ==================== 插件钩子 ====================

    async def on_context_overflow(self, token_count: int) -> bool:
        """处理上下文溢出"""
        if not self._compactor or not self.context.engine:
            return False

        context = self.context.engine.context
        messages = context.messages

        if not self._compactor.should_compact(messages):
            return False

        self.context.logger.info(
            f"Context compaction triggered: strategy={self._strategy}, tokens={token_count}"
        )

        try:
            result = await self._compactor.compact(messages)
            if result.removed_messages > 0:
                # 更新上下文
                context.messages = self._compactor.build_compacted_messages(
                    messages, result
                )

                # 记录压缩历史（用于自适应调整）
                if self._dynamic_config:
                    self._dynamic_config.record_compaction(result)

                self.context.logger.info(
                    f"Context compacted: saved={result.tokens_saved} tokens, "
                    f"removed={result.removed_messages} messages"
                )
                return True
        except Exception as e:
            self.context.logger.error(f"Compaction failed: {e}")

        return False

    async def on_before_llm_call(self, messages: list) -> list | None:
        """LLM 调用前的钩子 - 可用于主动压缩检查"""
        # 可以在这里添加主动压缩逻辑
        # 例如：在每次 LLM 调用前检查是否需要压缩
        return None
