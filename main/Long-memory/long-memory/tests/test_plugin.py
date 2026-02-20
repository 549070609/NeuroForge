"""
插件测试
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PLUGIN import LongMemoryPlugin, create_plugin
from config import LongMemoryConfig


class TestLongMemoryPlugin:
    """测试长记忆插件"""

    def test_metadata(self):
        """测试元数据"""
        plugin = LongMemoryPlugin()

        assert plugin.metadata.id == "tool.long-memory"
        assert plugin.metadata.version == "1.0.0"
        assert "tool.local-embeddings" in plugin.metadata.dependencies

    def test_create_plugin(self):
        """测试创建插件"""
        plugin = create_plugin()
        assert isinstance(plugin, LongMemoryPlugin)

    @pytest.mark.asyncio
    async def test_on_plugin_load(self):
        """测试插件加载"""
        plugin = LongMemoryPlugin()

        context = MagicMock()
        context.config = {
            "persist_directory": "/test/path",
        }
        context.engine = None

        await plugin.on_plugin_load(context)

        assert plugin._config is not None
        assert plugin._config.persist_directory == "/test/path"

    @pytest.mark.asyncio
    async def test_get_tools_without_vector_store(self):
        """测试未初始化向量存储时获取工具"""
        plugin = LongMemoryPlugin()
        tools = plugin.get_tools()

        # 未初始化时应该返回空列表
        assert tools == []

    @pytest.mark.asyncio
    async def test_get_tools_with_vector_store(self):
        """测试获取工具"""
        plugin = LongMemoryPlugin()
        plugin._config = LongMemoryConfig()
        plugin._embeddings_provider = MagicMock()

        await plugin.on_plugin_activate()

        tools = plugin.get_tools()

        assert len(tools) == 4
        tool_names = [t.name for t in tools]
        assert "memory_store" in tool_names
        assert "memory_search" in tool_names
        assert "memory_delete" in tool_names
        assert "memory_list" in tool_names


class TestTools:
    """测试工具类"""

    @pytest.fixture
    def mock_store(self):
        """模拟向量存储"""
        store = MagicMock()
        store.store = AsyncMock(return_value="mem_test123")
        store.search = AsyncMock(return_value=[])
        store.delete = AsyncMock(return_value=1)
        store.list_memories = AsyncMock(return_value=[])
        store.get_stats = AsyncMock()
        return store

    @pytest.fixture
    def config(self):
        """配置"""
        return LongMemoryConfig()

    @pytest.mark.asyncio
    async def test_memory_store_tool(self, mock_store, config):
        """测试存储工具"""
        from tools import MemoryStoreTool

        tool = MemoryStoreTool(mock_store, config, "session_123")

        result = await tool.execute(
            content="test content",
            importance=0.8,
            tags=["test"],
        )

        assert "已存储记忆" in result
        assert "mem_test123" in result
        mock_store.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_search_tool(self, mock_store, config):
        """测试搜索工具"""
        from tools import MemorySearchTool
        from models import MemoryEntry, MemorySearchResult

        # 设置模拟返回
        entry = MemoryEntry(content="test result", importance=0.7)
        mock_store.search.return_value = [MemorySearchResult(entry=entry, score=0.9)]

        tool = MemorySearchTool(mock_store, config)

        result = await tool.execute(query="test query")

        assert "找到" in result or "test result" in result
        mock_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_delete_tool(self, mock_store, config):
        """测试删除工具"""
        from tools import MemoryDeleteTool

        tool = MemoryDeleteTool(mock_store, config)

        # 未确认
        result = await tool.execute(confirm=False, memory_ids=["mem_123"])
        assert "未确认" in result

        # 确认删除
        result = await tool.execute(confirm=True, memory_ids=["mem_123"])
        assert "已删除" in result
        mock_store.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_memory_list_tool(self, mock_store, config):
        """测试列表工具"""
        from tools import MemoryListTool
        from models import MemoryStats

        # 测试统计
        mock_store.get_stats.return_value = MemoryStats(
            total_count=10,
            by_type={"knowledge": 8, "user": 2},
            avg_importance=0.65,
        )

        tool = MemoryListTool(mock_store, config)

        result = await tool.execute(action="stats")

        assert "统计信息" in result
        assert "10" in result

        # 测试列表
        mock_store.list_memories.return_value = [
            MemoryEntry(content="Memory 1"),
            MemoryEntry(content="Memory 2"),
        ]

        result = await tool.execute(action="list", limit=10)

        assert "Memory 1" in result
