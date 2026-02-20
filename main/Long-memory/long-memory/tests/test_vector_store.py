"""
向量存储测试
"""

import pytest
import tempfile
import os
import sys
from unittest.mock import MagicMock

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LongMemoryConfig
from models import MemoryEntry, MessageType, MemorySource
from vector_store import ChromaVectorStore, LocalEmbeddingFunction


class MockEmbeddingsProvider:
    """模拟嵌入提供者"""

    def embed_sync(self, texts):
        """返回模拟的嵌入向量"""
        return [[0.1] * 384 for _ in texts]


class TestLocalEmbeddingFunction:
    """测试嵌入函数适配器"""

    def test_call(self):
        """测试调用"""
        provider = MockEmbeddingsProvider()
        func = LocalEmbeddingFunction(provider)

        texts = ["hello", "world"]
        result = func(texts)

        assert len(result) == 2
        assert len(result[0]) == 384


class TestMemoryEntry:
    """测试记忆条目"""

    def test_create(self):
        """测试创建"""
        entry = MemoryEntry(
            content="test content",
        )

        assert entry.id.startswith("mem_")
        assert entry.timestamp
        assert entry.message_type == MessageType.USER
        assert entry.source == MemorySource.MANUAL
        assert entry.importance == 0.5

    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        entry = MemoryEntry(
            content="test content",
            session_id="session_123",
            message_type=MessageType.KNOWLEDGE,
            source=MemorySource.AUTO,
            importance=0.8,
            tags=["test", "example"],
            metadata={"key": "value"},
        )

        # 序列化
        data = entry.to_dict()
        assert data["content"] == "test content"
        assert data["session_id"] == "session_123"
        assert data["message_type"] == "knowledge"
        assert data["importance"] == 0.8

        # 反序列化
        restored = MemoryEntry.from_dict(data)
        assert restored.content == entry.content
        assert restored.session_id == entry.session_id
        assert restored.message_type == entry.message_type
        assert restored.importance == entry.importance
        assert restored.tags == entry.tags

    def test_importance_clamp(self):
        """测试重要性范围限制"""
        entry = MemoryEntry(content="test", importance=1.5)
        assert entry.importance == 1.0

        entry = MemoryEntry(content="test", importance=-0.5)
        assert entry.importance == 0.0


class TestChromaVectorStore:
    """测试向量存储"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config(self, temp_dir):
        """配置"""
        return LongMemoryConfig(
            persist_directory=temp_dir,
            collection_name="test_memory",
        )

    @pytest.fixture
    def provider(self):
        """嵌入提供者"""
        return MockEmbeddingsProvider()

    @pytest.fixture
    def store(self, config, provider):
        """向量存储"""
        return ChromaVectorStore(config, provider)

    @pytest.mark.asyncio
    async def test_store(self, store):
        """测试存储"""
        entry = MemoryEntry(
            content="This is a test memory",
            message_type=MessageType.KNOWLEDGE,
            importance=0.8,
        )

        memory_id = await store.store(entry)
        assert memory_id.startswith("mem_")

    @pytest.mark.asyncio
    async def test_search(self, store):
        """测试搜索"""
        # 存储一些记忆
        entries = [
            MemoryEntry(content="用户偏好使用中文回答", importance=0.8),
            MemoryEntry(content="项目路径是 /home/user/projects", importance=0.6),
            MemoryEntry(content="今天天气不错", importance=0.3),
        ]

        for entry in entries:
            await store.store(entry)

        # 搜索
        results = await store.search("用户偏好", n_results=2)

        assert len(results) >= 1
        # 第一个结果应该是最相关的
        assert results[0].entry.content == "用户偏好使用中文回答"

    @pytest.mark.asyncio
    async def test_delete_by_id(self, store):
        """测试按ID删除"""
        entry = MemoryEntry(content="to be deleted")
        memory_id = await store.store(entry)

        # 删除
        count = await store.delete(ids=[memory_id])
        assert count == 1

        # 验证已删除
        stats = await store.get_stats()
        # 可能还有其他记忆，所以只验证删除的确实不在了
        restored = await store.get_by_id(memory_id)
        assert restored is None

    @pytest.mark.asyncio
    async def test_list_memories(self, store):
        """测试列出记忆"""
        # 存储一些记忆
        for i in range(5):
            await store.store(MemoryEntry(content=f"Memory {i}"))

        # 列出
        memories = await store.list_memories(limit=3)
        assert len(memories) == 3

    @pytest.mark.asyncio
    async def test_get_stats(self, store):
        """测试获取统计"""
        # 存储一些不同类型的记忆
        await store.store(MemoryEntry(content="user message", message_type=MessageType.USER))
        await store.store(MemoryEntry(content="knowledge", message_type=MessageType.KNOWLEDGE))
        await store.store(MemoryEntry(content="assistant reply", message_type=MessageType.ASSISTANT))

        stats = await store.get_stats()

        assert stats.total_count == 3
        assert "user" in stats.by_type
        assert "knowledge" in stats.by_type

    @pytest.mark.asyncio
    async def test_clear(self, store):
        """测试清空"""
        # 存储一些记忆
        for i in range(3):
            await store.store(MemoryEntry(content=f"Memory {i}"))

        # 清空
        count = await store.clear()
        assert count == 3

        # 验证已清空
        stats = await store.get_stats()
        assert stats.total_count == 0


class TestLongMemoryConfig:
    """测试配置"""

    def test_default_values(self):
        """测试默认值"""
        config = LongMemoryConfig()
        assert config.persist_directory == "./data/chroma"
        assert config.collection_name == "long_memory"
        assert config.default_search_limit == 5

    def test_from_dict(self):
        """测试从字典创建"""
        config = LongMemoryConfig.from_dict({
            "persist_directory": "/custom/path",
            "default_search_limit": 10,
        })

        assert config.persist_directory == "/custom/path"
        assert config.default_search_limit == 10

    def test_validate(self):
        """测试验证"""
        # 有效配置
        config = LongMemoryConfig()
        errors = config.validate()
        assert len(errors) == 0

        # 无效配置
        config = LongMemoryConfig(default_search_limit=-1)
        errors = config.validate()
        assert len(errors) > 0
