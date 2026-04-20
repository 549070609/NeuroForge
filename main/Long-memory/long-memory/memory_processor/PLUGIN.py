"""
记忆加工插件

在记忆存入后自动整理标签、主题和摘要
"""

from typing import Any, Dict, List, Optional
import logging

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType, PluginContext
from pyagentforge.tools.base import BaseTool

from .config import ProcessorConfig
from .processor_engine import ProcessorEngine
from .tools import MemoryProcessTool, MemoryReprocessTool

logger = logging.getLogger(__name__)


class MemoryProcessorPlugin(Plugin):
    """记忆加工插件"""

    metadata = PluginMetadata(
        id="tool.memory-processor",
        name="Memory Processor",
        version="1.0.0",
        type=PluginType.TOOL,
        description="记忆加工插件，在记忆存入后自动整理标签、主题和摘要",
        author="Local",
        dependencies=["tool.long-memory"],
        optional_dependencies=[],
        provides=["memory.processing", "memory.auto_tagging"],
        conflicts=[],
        priority=15,  # 在长记忆插件之后加载
    )

    def __init__(self):
        super().__init__()
        self._config: ProcessorConfig = None
        self._engine: ProcessorEngine = None
        self._long_memory_plugin: Optional[Any] = None
        self._llm_client: Optional[Any] = None

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载"""
        await super().on_plugin_load(context)

        # 解析配置
        config_dict = context.config or {}
        self._config = ProcessorConfig.from_dict(config_dict)

        # 验证配置
        errors = self._config.validate()
        if errors:
            logger.warning(f"Memory processor config validation errors: {errors}")

        # 获取 LLM 客户端
        self._llm_client = self._get_llm_client(context)

        logger.info(
            f"MemoryProcessorPlugin loaded, enabled={self._config.enabled}, "
            f"auto_trigger={self._config.auto_trigger}"
        )

    async def on_plugin_activate(self) -> None:
        """插件激活"""
        await super().on_plugin_activate()

        # 如果未启用，跳过激活
        if not self._config.enabled:
            logger.info("MemoryProcessorPlugin is disabled, skipping activation")
            return

        # 获取长记忆插件
        self._long_memory_plugin = self._get_long_memory_plugin()

        if not self._long_memory_plugin:
            logger.warning(
                "Long-memory plugin not available. "
                "Memory processor will not work."
            )
            return

        # 获取向量存储
        vector_store = self._long_memory_plugin.get_vector_store()
        if not vector_store:
            logger.error("Failed to get vector store from long-memory plugin")
            return

        # 初始化引擎
        self._engine = ProcessorEngine(
            vector_store=vector_store,
            config=self._config,
            llm_client=self._llm_client,
        )

        logger.info("MemoryProcessorPlugin activated and engine initialized")

    def get_tools(self) -> List[BaseTool]:
        """返回提供的工具"""
        if not self._config.enabled or self._engine is None:
            return []

        return [
            MemoryProcessTool(self._engine),
            MemoryReprocessTool(self._engine),
        ]

    # ============ 钩子方法 ============

    async def on_after_tool_call(
        self,
        tool_name: str,
        result: Any,
        **kwargs,
    ) -> Optional[Any]:
        """
        工具调用后钩子

        在 memory_store 后自动触发加工
        """
        # 检查是否启用自动触发
        if not self._config.enabled or not self._config.auto_trigger:
            return None

        # 只处理 memory_store 工具
        if tool_name != "memory_store":
            return None

        if self._engine is None:
            logger.warning("Engine not initialized, skipping auto-processing")
            return None

        # 从结果中提取 memory_id
        memory_id = self._extract_memory_id(result)
        if not memory_id:
            logger.debug("Could not extract memory_id from store result")
            return None

        # 异步触发加工（不阻塞响应）
        try:
            logger.debug(f"Auto-processing memory: {memory_id}")
            process_result = await self._engine.process_by_id(memory_id)

            if process_result.success:
                # 返回附加信息，由调用方决定如何处理
                return {
                    "auto_processed": True,
                    "memory_id": memory_id,
                    "tags": process_result.analysis.tags if process_result.analysis else [],
                    "topic": process_result.analysis.topic if process_result.analysis else "",
                    "summary": process_result.analysis.summary if process_result.analysis else "",
                }
            else:
                logger.warning(f"Auto-processing failed for {memory_id}: {process_result.error}")

        except Exception as e:
            logger.error(f"Error in auto-processing: {e}")

        return None

    # ============ 公共 API ============

    @property
    def is_enabled(self) -> bool:
        """检查插件是否启用"""
        return self._config.enabled if self._config else False

    @property
    def engine(self) -> Optional[ProcessorEngine]:
        """获取加工引擎"""
        return self._engine

    async def process_memory(self, memory_id: str, force: bool = False) -> Dict[str, Any]:
        """
        加工指定记忆（公共 API）

        Args:
            memory_id: 记忆 ID
            force: 是否强制重新加工

        Returns:
            加工结果
        """
        if not self._config.enabled:
            raise RuntimeError("MemoryProcessorPlugin is disabled")

        if self._engine is None:
            raise RuntimeError("Processor engine not initialized")

        result = await self._engine.process_by_id(memory_id, force=force)
        return result.to_dict()

    async def reprocess_batch(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        批量重加工（公共 API）

        Args:
            limit: 最大处理数量

        Returns:
            加工结果列表
        """
        if not self._config.enabled:
            raise RuntimeError("MemoryProcessorPlugin is disabled")

        if self._engine is None:
            raise RuntimeError("Processor engine not initialized")

        results = await self._engine.reprocess_unprocessed(limit=limit)
        return [r.to_dict() for r in results]

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

    def _get_llm_client(self, context: PluginContext) -> Optional[Any]:
        """获取 LLM 客户端"""
        if context.engine is None:
            return None

        # 从引擎获取 provider
        provider = getattr(context.engine, "provider", None)
        if provider is None:
            provider = getattr(context.engine, "_provider", None)

        return provider

    def _extract_memory_id(self, result: Any) -> Optional[str]:
        """
        从存储结果中提取 memory_id

        Args:
            result: 工具调用结果

        Returns:
            memory_id 或 None
        """
        if isinstance(result, str):
            # 尝试从字符串中解析 ID
            # 格式: "已存储记忆 (ID: mem_xxx)"
            import re
            match = re.search(r'ID:\s*(mem_\w+)', result)
            if match:
                return match.group(1)

        elif isinstance(result, dict):
            # 字典格式
            return result.get("memory_id") or result.get("id")

        elif hasattr(result, "id"):
            # 对象格式
            return result.id

        return None


# 插件入口点
def create_plugin() -> Plugin:
    """创建插件实例"""
    return MemoryProcessorPlugin()
