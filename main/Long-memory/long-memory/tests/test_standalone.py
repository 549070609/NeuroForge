"""Standalone smoke tests for long-memory components."""

from __future__ import annotations

import asyncio
import gc
import os
import shutil
import sys
import tempfile
import time

# Add plugin root to path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LongMemoryConfig
from models import MemoryEntry, MemorySource, MessageType
from vector_store import ChromaVectorStore


class MockEmbeddingsProvider:
    """Simple deterministic embedding provider."""

    def embed_sync(self, texts):
        return [[0.1] * 384 for _ in texts]


async def test_basic_operations():
    """Run end-to-end store/search/list/delete/clear flow."""

    tmpdir = tempfile.mkdtemp()
    store = None
    try:
        config = LongMemoryConfig(
            persist_directory=tmpdir,
            collection_name="test_memory",
        )
        provider = MockEmbeddingsProvider()
        store = ChromaVectorStore(config, provider)

        entry1 = MemoryEntry(
            content="user prefers Chinese responses",
            message_type=MessageType.KNOWLEDGE,
            importance=0.8,
            tags=["preference", "language"],
        )
        id1 = await store.store(entry1)

        entry2 = MemoryEntry(
            content="project path is /home/user/projects",
            message_type=MessageType.KNOWLEDGE,
            importance=0.6,
            tags=["path"],
        )
        id2 = await store.store(entry2)

        results = await store.search("user prefers", n_results=5)
        assert len(results) >= 1

        memories = await store.list_memories(limit=10)
        assert len(memories) == 2

        stats = await store.get_stats()
        assert stats.total_count == 2

        fetched = await store.get_by_id(id1)
        assert fetched is not None

        delete_count = await store.delete(ids=[id2])
        assert delete_count == 1
        deleted = await store.get_by_id(id2)
        assert deleted is None

        clear_count = await store.clear()
        assert clear_count >= 1
        final_stats = await store.get_stats()
        assert final_stats.total_count == 0
    finally:
        if store is not None:
            store.close()
        gc.collect()
        for attempt in range(8):
            try:
                shutil.rmtree(tmpdir)
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.25 * (attempt + 1))
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)


def test_models():
    """Verify model serialization and clamping."""

    entry = MemoryEntry(
        content="test content",
        session_id="session_123",
        message_type=MessageType.KNOWLEDGE,
        source=MemorySource.MANUAL,
        importance=0.9,
        tags=["test"],
    )

    data = entry.to_dict()
    restored = MemoryEntry.from_dict(data)
    assert restored.content == entry.content

    entry_high = MemoryEntry(content="test", importance=1.5)
    assert entry_high.importance == 1.0

    entry_low = MemoryEntry(content="test", importance=-0.5)
    assert entry_low.importance == 0.0


def test_config():
    """Verify default and dict-based config behaviors."""

    config = LongMemoryConfig()
    assert config.persist_directory == "./data/chroma"
    assert config.default_search_limit == 5

    custom = LongMemoryConfig.from_dict(
        {
            "persist_directory": "/custom/path",
            "default_search_limit": 10,
        }
    )
    assert custom.persist_directory == "/custom/path"
    assert custom.default_search_limit == 10

    errors = custom.validate()
    assert len(errors) == 0


if __name__ == "__main__":
    test_config()
    test_models()
    asyncio.run(test_basic_operations())
