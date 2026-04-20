"""Vector store tests."""

from __future__ import annotations

import gc
import hashlib
import os
import shutil
import sys
import tempfile
import time
from typing import List

import numpy as np
import pytest

# Add plugin root to path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LongMemoryConfig
from models import MemoryEntry, MemorySource, MessageType
from vector_store import ChromaVectorStore, LocalEmbeddingFunction


class MockEmbeddingsProvider:
    """Deterministic embedding provider for stable test ranking."""

    _DIM = 384

    def embed_sync(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vec = np.zeros(self._DIM, dtype=float)
            for token in text.lower().split():
                idx = int.from_bytes(
                    hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(),
                    "little",
                ) % self._DIM
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec.tolist())
        return vectors


class TestLocalEmbeddingFunction:
    """Tests for embedding adapter."""

    def test_call(self):
        provider = MockEmbeddingsProvider()
        func = LocalEmbeddingFunction(provider)

        result = func(["hello", "world"])

        assert len(result) == 2
        assert len(result[0]) == 384


class TestMemoryEntry:
    """Tests for memory entry model."""

    def test_create(self):
        entry = MemoryEntry(content="test content")

        assert entry.id.startswith("mem_")
        assert entry.timestamp
        assert entry.message_type == MessageType.USER
        assert entry.source == MemorySource.MANUAL
        assert entry.importance == 0.5

    def test_to_dict_and_from_dict(self):
        entry = MemoryEntry(
            content="test content",
            session_id="session_123",
            message_type=MessageType.KNOWLEDGE,
            source=MemorySource.AUTO,
            importance=0.8,
            tags=["test", "example"],
            metadata={"key": "value"},
        )

        data = entry.to_dict()
        assert data["content"] == "test content"
        assert data["session_id"] == "session_123"
        assert data["message_type"] == "knowledge"
        assert data["importance"] == 0.8

        restored = MemoryEntry.from_dict(data)
        assert restored.content == entry.content
        assert restored.session_id == entry.session_id
        assert restored.message_type == entry.message_type
        assert restored.importance == entry.importance
        assert restored.tags == entry.tags

    def test_importance_clamp(self):
        high_entry = MemoryEntry(content="test", importance=1.5)
        assert high_entry.importance == 1.0

        low_entry = MemoryEntry(content="test", importance=-0.5)
        assert low_entry.importance == 0.0


class TestChromaVectorStore:
    """Tests for Chroma vector store."""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        try:
            yield tmpdir
        finally:
            gc.collect()
            for attempt in range(8):
                try:
                    shutil.rmtree(tmpdir)
                    break
                except PermissionError:
                    gc.collect()
                    time.sleep(0.25 * (attempt + 1))
            else:
                # 最后尝试忽略错误，避免 Windows mmap 残留阻塞用例
                shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def config(self, temp_dir):
        return LongMemoryConfig(
            persist_directory=temp_dir,
            collection_name="test_memory",
        )

    @pytest.fixture
    def provider(self):
        return MockEmbeddingsProvider()

    @pytest.fixture
    def store(self, config, provider):
        vector_store = ChromaVectorStore(config, provider)
        try:
            yield vector_store
        finally:
            vector_store.close()
            gc.collect()

    @pytest.mark.asyncio
    async def test_store(self, store):
        entry = MemoryEntry(
            content="This is a test memory",
            message_type=MessageType.KNOWLEDGE,
            importance=0.8,
        )

        memory_id = await store.store(entry)
        assert memory_id.startswith("mem_")

    @pytest.mark.asyncio
    async def test_search(self, store):
        entries = [
            MemoryEntry(content="user prefers Chinese responses", importance=0.8),
            MemoryEntry(content="project path is /home/user/projects", importance=0.6),
            MemoryEntry(content="today's weather is nice", importance=0.3),
        ]

        for entry in entries:
            await store.store(entry)

        results = await store.search("user prefers", n_results=2)

        assert len(results) >= 1
        assert any(result.entry.content == entries[0].content for result in results)

    @pytest.mark.asyncio
    async def test_delete_by_id(self, store):
        entry = MemoryEntry(content="to be deleted")
        memory_id = await store.store(entry)

        count = await store.delete(ids=[memory_id])
        assert count == 1

        restored = await store.get_by_id(memory_id)
        assert restored is None

    @pytest.mark.asyncio
    async def test_list_memories(self, store):
        for i in range(5):
            await store.store(MemoryEntry(content=f"Memory {i}"))

        memories = await store.list_memories(limit=3)
        assert len(memories) == 3

    @pytest.mark.asyncio
    async def test_get_stats(self, store):
        await store.store(MemoryEntry(content="user", message_type=MessageType.USER))
        await store.store(
            MemoryEntry(content="knowledge", message_type=MessageType.KNOWLEDGE)
        )
        await store.store(
            MemoryEntry(content="assistant", message_type=MessageType.ASSISTANT)
        )

        stats = await store.get_stats()

        assert stats.total_count == 3
        assert "user" in stats.by_type
        assert "knowledge" in stats.by_type

    @pytest.mark.asyncio
    async def test_clear(self, store):
        for i in range(3):
            await store.store(MemoryEntry(content=f"Memory {i}"))

        count = await store.clear()
        assert count == 3

        stats = await store.get_stats()
        assert stats.total_count == 0


class TestLongMemoryConfig:
    """Tests for config model."""

    def test_default_values(self):
        config = LongMemoryConfig()
        assert config.persist_directory == "./data/chroma"
        assert config.collection_name == "long_memory"
        assert config.default_search_limit == 5

    def test_from_dict(self):
        config = LongMemoryConfig.from_dict(
            {
                "persist_directory": "/custom/path",
                "default_search_limit": 10,
            }
        )

        assert config.persist_directory == "/custom/path"
        assert config.default_search_limit == 10

    def test_validate(self):
        config = LongMemoryConfig()
        errors = config.validate()
        assert len(errors) == 0

        invalid_config = LongMemoryConfig(default_search_limit=-1)
        errors = invalid_config.validate()
        assert len(errors) > 0
