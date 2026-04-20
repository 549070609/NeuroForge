"""
Long Memory 插件

基于 ChromaDB 的长记忆系统，提供语义搜索和持久化存储。
"""

from typing import List
import logging

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType, PluginContext
from pyagentforge.tools.base import BaseTool

try:
    from .config import LongMemoryConfig
    from .vector_store import ChromaVectorStore
    from .tools import MemoryDeleteTool, MemoryListTool, MemorySearchTool, MemoryStoreTool
except ImportError:
    # 支持独立运行时导入（tests 直接 import PLUGIN）
    from config import LongMemoryConfig
    from vector_store import ChromaVectorStore
    from tools import MemoryDeleteTool, MemoryListTool, MemorySearchTool, MemoryStoreTool

logger = logging.getLogger(__name__)


class LongMemoryPlugin(Plugin):
    """长记忆插件"""

    metadata = PluginMetadata(
        id="tool.long-memory",
        name="Long Memory",
        version="1.0.0",
        type=PluginType.TOOL,
        description="基于 ChromaDB 的长记忆系统，提供语义搜索和持久化存储",
        author="Local",
        dependencies=["tool.local-embeddings"],  # 依赖嵌入插件
        optional_dependencies=[],
        provides=["memory.vector", "memory.semantic_search", "memory.long_term"],
        conflicts=[],
        priority=10,  # 在嵌入插件之后加载
    )

    def __init__(self):
        super().__init__()
        self._config: LongMemoryConfig = None
        self._vector_store: ChromaVectorStore = None
        self._embeddings_provider = None
        self._session_id: str = ""

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载"""
        await super().on_plugin_load(context)

        # 解析配置
        config_dict = context.config or {}
        self._config = LongMemoryConfig.from_dict(config_dict)

        # 验证配置
        errors = self._config.validate()
        if errors:
            logger.warning(f"Long memory config validation errors: {errors}")

        # 从引擎获取嵌入提供者
        await self._get_embeddings_provider(context)

        logger.info(
            f"LongMemoryPlugin loaded, persist_directory={self._config.persist_directory}"
        )

    async def _get_embeddings_provider(self, context: PluginContext) -> None:
        """从嵌入插件获取 EmbeddingsProvider"""
        engine = context.engine

        if not engine:
            logger.warning("Engine not available, cannot get embeddings provider")
            return

        # 尝试从插件管理器获取嵌入插件
        plugin_manager = getattr(engine, "_plugin_manager", None)
        if not plugin_manager:
            logger.warning("Plugin manager not available")
            return

        # 查找嵌入插件
        embeddings_plugin = None
        for plugin in plugin_manager._plugins.values():
            if hasattr(plugin, "metadata") and plugin.metadata.id == "tool.local-embeddings":
                embeddings_plugin = plugin
                break

        if embeddings_plugin and hasattr(embeddings_plugin, "get_embeddings_provider"):
            self._embeddings_provider = embeddings_plugin.get_embeddings_provider()
            logger.info("Got embeddings provider from local-embeddings plugin")
        else:
            logger.warning(
                "Could not get embeddings provider from local-embeddings plugin. "
                "Make sure the plugin is loaded first."
            )

    async def on_plugin_activate(self) -> None:
        """插件激活"""
        await super().on_plugin_activate()

        if self._embeddings_provider:
            # 初始化向量存储
            self._vector_store = ChromaVectorStore(
                config=self._config,
                embeddings_provider=self._embeddings_provider,
            )
            logger.info("ChromaVectorStore initialized")
        else:
            logger.error(
                "Cannot activate: embeddings provider not available. "
                "Ensure local-embeddings plugin is loaded."
            )

    async def on_engine_start(self, engine) -> None:
        """引擎启动时，获取会话 ID"""
        # 尝试从引擎获取当前会话 ID
        if hasattr(engine, "_session_id"):
            self._session_id = engine._session_id
        elif hasattr(engine, "session_id"):
            self._session_id = engine.session_id

    def get_tools(self) -> List[BaseTool]:
        """返回插件提供的工具"""
        if not self._vector_store:
            logger.warning("Vector store not initialized, tools will not work")
            return []

        return [
            MemoryStoreTool(self._vector_store, self._config, self._session_id),
            MemorySearchTool(self._vector_store, self._config),
            MemoryDeleteTool(self._vector_store, self._config),
            MemoryListTool(self._vector_store, self._config),
        ]

    def get_embeddings_provider(self):
        """获取嵌入提供者（供其他插件使用）"""
        return self._embeddings_provider

    def get_vector_store(self) -> ChromaVectorStore:
        """获取向量存储（供其他插件使用）"""
        return self._vector_store


# 插件入口点
def create_plugin() -> Plugin:
    """创建插件实例"""
    return LongMemoryPlugin()
