"""
超级压缩插件

智能压缩对话历史，与长记忆联动，实现:
- 自动/手动压缩
- 多策略摘要生成
- 与长记忆无缝集成
- 上下文溢出自动处理

注意: 此插件默认关闭，需要在配置中显式启用
"""

from typing import Any, Optional

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool

from .budget_manager import TokenBudgetManager
from .summary_generator import SummaryGenerator, SummaryStrategy
from .compress_engine import CompressEngine
from .tools.compress_tool import CompressTool, CompressStatusTool

import logging

logger = logging.getLogger(__name__)


class SuperCompressPlugin(Plugin):
    """超级压缩插件"""

    metadata = PluginMetadata(
        id="tool.super-compress",
        name="Super Compress",
        version="1.0.0",
        type=PluginType.TOOL,
        description="智能压缩对话历史，与长记忆联动，实现无限对话能力（默认关闭，需配置启用）",
        author="Local",
        provides=["compression"],
        dependencies=["tool.long-memory"],
        optional_dependencies=[],
        priority=20,  # 在长记忆插件之后加载
    )

    def __init__(self):
        super().__init__()
        self._budget_manager: Optional[TokenBudgetManager] = None
        self._summary_generator: Optional[SummaryGenerator] = None
        self._compress_engine: Optional[CompressEngine] = None
        self._long_memory: Optional[Any] = None
        self._model: str = "default"
        self._messages: list[dict[str, Any]] = []
        self._enabled: bool = False  # 默认关闭
        self._auto_compress: bool = False  # 默认关闭自动压缩

    async def on_plugin_load(self, context) -> None:
        """插件加载"""
        await super().on_plugin_load(context)

        # 获取配置
        config = context.config or {}

        # 检查是否启用（默认关闭）
        self._enabled = config.get("enabled", False)

        if not self._enabled:
            logger.info(
                "SuperCompressPlugin is disabled. "
                "Set 'enabled: true' in config to enable."
            )
            return

        compression_config = config.get("compression", {})
        summary_config = config.get("summary", {})

        # 读取配置
        self._model = compression_config.get("model", "default")
        compress_threshold = compression_config.get("compress_threshold", 0.8)
        keep_recent = compression_config.get("keep_recent", 20)
        self._auto_compress = compression_config.get("auto_compress", False)  # 默认关闭

        # 摘要配置
        default_strategy = SummaryStrategy(
            summary_config.get("strategy", "smart")
        )
        max_summary_tokens = summary_config.get("max_tokens", 2000)

        # 初始化组件
        self._budget_manager = TokenBudgetManager(
            model=self._model,
            compress_threshold=compress_threshold,
        )

        self._summary_generator = SummaryGenerator(
            llm_client=self._get_llm_client(context),
            default_strategy=default_strategy,
            max_summary_tokens=max_summary_tokens,
        )

        # 长记忆插件稍后在 activate 时获取
        self._compress_engine = CompressEngine(
            budget_manager=self._budget_manager,
            summary_generator=self._summary_generator,
            long_memory_plugin=None,  # 稍后设置
            keep_recent=keep_recent,
        )

        logger.info(
            f"SuperCompressPlugin enabled and loaded, model={self._model}, "
            f"threshold={compress_threshold}, auto_compress={self._auto_compress}"
        )

    async def on_plugin_activate(self) -> None:
        """插件激活"""
        await super().on_plugin_activate()

        # 如果未启用，跳过激活
        if not self._enabled:
            return

        # 获取长记忆插件
        self._long_memory = self._get_long_memory_plugin()

        if self._long_memory:
            # 更新压缩引擎的长记忆引用
            self._compress_engine.long_memory = self._long_memory
            logger.info("Connected to long-memory plugin")
        else:
            logger.warning(
                "Long-memory plugin not available. Compression summaries will not be stored."
            )

    def get_tools(self) -> list[BaseTool]:
        """返回提供的工具"""
        # 如果未启用，不提供工具
        if not self._enabled or self._compress_engine is None:
            return []

        return [
            CompressTool(
                engine=self._compress_engine,
                get_messages_func=self._get_messages,
                set_messages_func=self._set_messages,
            ),
            CompressStatusTool(
                budget_manager=self._budget_manager,
                engine=self._compress_engine,
                get_messages_func=self._get_messages,
            ),
        ]

    # ============ 钩子方法 ============

    async def on_before_llm_call(self, messages: list) -> Optional[list]:
        """
        LLM 调用前钩子

        自动压缩检测
        """
        # 如果未启用，直接返回
        if not self._enabled:
            return None

        # 更新消息引用
        self._messages = messages

        # 自动压缩检测
        if self._auto_compress and self._compress_engine:
            if self._budget_manager.should_compress(messages):
                logger.info("Auto-compression triggered")

                result = await self._compress_engine.compress(
                    messages=messages,
                    force=False,
                    store_to_memory=True,
                )

                # 更新消息
                self._messages = result.compressed_messages
                return result.compressed_messages

        return None

    async def on_context_overflow(self, token_count: int) -> bool:
        """
        上下文溢出钩子

        紧急压缩处理
        """
        # 如果未启用，不处理
        if not self._enabled or self._compress_engine is None:
            return False

        logger.warning(
            f"Context overflow detected (tokens={token_count}), forcing compression"
        )

        try:
            # 强制压缩
            result = await self._compress_engine.compress(
                messages=self._messages,
                force=True,
                store_to_memory=True,
            )

            # 更新消息
            self._messages = result.compressed_messages

            # 通知已处理
            return True

        except Exception as e:
            logger.error(f"Emergency compression failed: {e}")
            return False

    # ============ 公共 API ============

    @property
    def is_enabled(self) -> bool:
        """检查插件是否启用"""
        return self._enabled

    @property
    def engine(self) -> Optional[CompressEngine]:
        """获取压缩引擎"""
        return self._compress_engine

    async def compress(
        self,
        messages: list[dict[str, Any]],
        force: bool = False,
        store_to_memory: bool = True,
    ) -> dict[str, Any]:
        """
        执行压缩 (公共 API)

        Args:
            messages: 消息列表
            force: 强制压缩
            store_to_memory: 存储到长记忆

        Returns:
            压缩结果
        """
        if not self._enabled:
            raise RuntimeError("SuperCompressPlugin is disabled")

        if self._compress_engine is None:
            raise RuntimeError("Compress engine not initialized")

        result = await self._compress_engine.compress(
            messages=messages,
            force=force,
            store_to_memory=store_to_memory,
        )

        return {
            "compressed_messages": result.compressed_messages,
            "original_count": result.original_count,
            "compressed_count": result.compressed_count,
            "compression_ratio": result.compression_ratio,
            "summary_stored": result.summary_stored,
            "summary_id": result.summary_id,
        }

    def get_budget_status(self, messages: list[dict[str, Any]]) -> str:
        """获取预算状态"""
        if not self._enabled:
            return "SuperCompressPlugin is disabled"
        if self._budget_manager is None:
            return "Budget manager not initialized"
        return self._budget_manager.get_budget_status(messages)

    # ============ 内部方法 ============

    def _get_long_memory_plugin(self) -> Optional[Any]:
        """获取长记忆插件实例"""
        if self._context is None or self._context.engine is None:
            return None

        engine = self._context.engine

        # 从插件管理器获取
        plugin_manager = getattr(engine, "_plugin_manager", None)
        if plugin_manager is None:
            plugin_manager = getattr(engine, "plugin_manager", None)

        if plugin_manager is None:
            return None

        # 查找长记忆插件
        for plugin in getattr(plugin_manager, "_plugins", {}).values():
            if hasattr(plugin, "metadata") and plugin.metadata.id == "tool.long-memory":
                return plugin

        return None

    def _get_llm_client(self, context) -> Optional[Any]:
        """获取 LLM 客户端"""
        if context.engine is None:
            return None

        # 从引擎获取 provider
        return getattr(context.engine, "provider", None)

    def _get_messages(self) -> list[dict[str, Any]]:
        """获取当前消息列表"""
        return self._messages

    def _set_messages(self, messages: list[dict[str, Any]]) -> None:
        """设置消息列表"""
        self._messages = messages


# 插件入口点
def create_plugin() -> Plugin:
    """创建插件实例"""
    return SuperCompressPlugin()
