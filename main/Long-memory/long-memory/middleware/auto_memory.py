"""
自动记忆中间件

监听对话，自动将重要内容存储到长记忆系统
"""

from typing import Any, Optional
import logging

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType, PluginContext

from ..config import LongMemoryConfig
from ..models import MemoryEntry, MessageType, MemorySource
from ..vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class AutoMemoryMiddleware(Plugin):
    """自动记忆中间件"""

    metadata = PluginMetadata(
        id="middleware.auto-memory",
        name="Auto Memory Middleware",
        version="1.0.0",
        type=PluginType.MIDDLEWARE,
        description="自动将重要对话存储到长记忆系统",
        author="Local",
        dependencies=["tool.long-memory"],
        optional_dependencies=[],
        provides=["middleware.auto_memory"],
        conflicts=[],
        priority=5,  # 在长记忆插件之后
    )

    def __init__(self):
        super().__init__()
        self._config: LongMemoryConfig = None
        self._vector_store: ChromaVectorStore = None
        self._session_id: str = ""

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载"""
        await super().on_plugin_load(context)

        # 从配置中获取自动记忆配置
        # 注意：配置来自 tool.long-memory
        engine = context.engine
        plugin_manager = getattr(engine, "_plugin_manager", None)

        if plugin_manager:
            # 查找长记忆插件
            for plugin in plugin_manager._plugins.values():
                if hasattr(plugin, "metadata") and plugin.metadata.id == "tool.long-memory":
                    self._vector_store = plugin.get_vector_store()
                    # 获取配置（这里我们使用长记忆插件的配置）
                    if hasattr(plugin, "_config"):
                        self._config = plugin._config
                    break

        if not self._config:
            # 使用默认配置
            self._config = LongMemoryConfig()
            logger.warning("Using default config for auto-memory middleware")

        logger.info(
            f"AutoMemoryMiddleware loaded, enabled={self._config.auto_memory_enabled}"
        )

    async def on_engine_start(self, engine) -> None:
        """引擎启动时，获取会话 ID"""
        if hasattr(engine, "_session_id"):
            self._session_id = engine._session_id
        elif hasattr(engine, "session_id"):
            self._session_id = engine.session_id

    async def on_after_llm_call(self, response) -> Optional[Any]:
        """LLM 调用后，自动存储重要内容"""

        if not self._config.auto_memory_enabled:
            return None

        if not self._vector_store:
            logger.warning("Vector store not available for auto-memory")
            return None

        # 获取消息内容
        # 假设 response 有 content 属性或可以直接转为字符串
        content = None
        if hasattr(response, "content"):
            content = response.content
        elif hasattr(response, "text"):
            content = response.text
        else:
            content = str(response) if response else None

        if not content:
            return None

        # 计算重要性
        importance = self._calculate_importance(content)

        if importance >= self._config.auto_memory_min_importance:
            # 自动存储
            entry = MemoryEntry(
                content=content,
                session_id=self._session_id,
                message_type=MessageType.ASSISTANT,
                source=MemorySource.AUTO,
                importance=importance,
                tags=["auto"],
            )

            try:
                memory_id = await self._vector_store.store(entry)
                logger.info(
                    f"Auto-stored memory: {memory_id} (importance={importance:.2f})"
                )
            except Exception as e:
                logger.error(f"Failed to auto-store memory: {e}")

        return None

    def _calculate_importance(self, content: str) -> float:
        """
        计算内容的重要性分数

        基于关键词匹配和内容特征

        Args:
            content: 消息内容

        Returns:
            重要性分数 0.0-1.0
        """
        if not content:
            return 0.0

        # 关键词权重
        keywords = self._config.auto_memory_keywords
        content_lower = content.lower()

        # 计算匹配的关键词数量
        matched = sum(1 for kw in keywords if kw.lower() in content_lower)

        # 基础分数
        base_score = 0.3

        # 关键词加分（每个关键词 +0.1，最多 +0.5）
        keyword_score = min(0.5, matched * 0.1)

        # 内容长度加分（较长内容可能更重要）
        length_score = 0.0
        if len(content) > 200:
            length_score = 0.1
        elif len(content) > 500:
            length_score = 0.15

        # 问号/感叹号加分（可能是重要声明或问题）
        punctuation_score = 0.0
        if "!" in content or "！" in content:
            punctuation_score += 0.05
        if "?" in content or "？" in content:
            punctuation_score += 0.03

        # 总分
        total_score = base_score + keyword_score + length_score + punctuation_score

        # 限制在 0-1 范围
        return max(0.0, min(1.0, total_score))


# 插件入口点
def create_plugin() -> Plugin:
    """创建插件实例"""
    return AutoMemoryMiddleware()
