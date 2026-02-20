"""
简单功能测试脚本

直接测试插件的核心功能
"""

import sys
import os
import tempfile
import asyncio

# 添加插件目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LongMemoryConfig
from models import MemoryEntry, MessageType, MemorySource
from vector_store import ChromaVectorStore, LocalEmbeddingFunction


class MockEmbeddingsProvider:
    """模拟嵌入提供者"""

    def embed_sync(self, texts):
        """返回模拟的嵌入向量"""
        return [[0.1] * 384 for _ in texts]


async def test_basic_operations():
    """测试基本操作"""
    print("=" * 50)
    print("测试基本操作")
    print("=" * 50)

    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\n使用临时目录: {tmpdir}")

        # 创建配置
        config = LongMemoryConfig(
            persist_directory=tmpdir,
            collection_name="test_memory",
        )
        print(f"配置: persist_directory={config.persist_directory}")

        # 创建模拟嵌入提供者
        provider = MockEmbeddingsProvider()

        # 创建向量存储
        store = ChromaVectorStore(config, provider)

        # 测试 1: 存储记忆
        print("\n--- 测试 1: 存储记忆 ---")
        entry1 = MemoryEntry(
            content="用户偏好使用中文回答问题",
            message_type=MessageType.KNOWLEDGE,
            importance=0.8,
            tags=["preference", "language"],
        )
        id1 = await store.store(entry1)
        print(f"存储记忆 ID: {id1}")

        entry2 = MemoryEntry(
            content="项目路径是 /home/user/projects",
            message_type=MessageType.KNOWLEDGE,
            importance=0.6,
            tags=["path"],
        )
        id2 = await store.store(entry2)
        print(f"存储记忆 ID: {id2}")

        # 测试 2: 搜索记忆
        print("\n--- 测试 2: 搜索记忆 ---")
        results = await store.search("用户偏好", n_results=5)
        print(f"搜索结果数量: {len(results)}")
        for i, result in enumerate(results):
            print(f"  {i+1}. [相似度: {result.score:.2%}] {result.entry.content[:50]}...")

        # 测试 3: 列出记忆
        print("\n--- 测试 3: 列出记忆 ---")
        memories = await store.list_memories(limit=10)
        print(f"记忆数量: {len(memories)}")
        for mem in memories:
            print(f"  - {mem.id}: {mem.content[:50]}...")

        # 测试 4: 获取统计
        print("\n--- 测试 4: 获取统计 ---")
        stats = await store.get_stats()
        print(f"总记忆数: {stats.total_count}")
        print(f"按类型: {stats.by_type}")
        print(f"平均重要性: {stats.avg_importance:.3f}")

        # 测试 5: 按 ID 获取
        print("\n--- 测试 5: 按 ID 获取 ---")
        fetched = await store.get_by_id(id1)
        print(f"获取记忆: {fetched.content if fetched else 'None'}")

        # 测试 6: 删除记忆
        print("\n--- 测试 6: 删除记忆 ---")
        count = await store.delete(ids=[id2])
        print(f"删除数量: {count}")

        # 验证删除
        deleted = await store.get_by_id(id2)
        print(f"删除后获取: {deleted}")

        # 测试 7: 清空
        print("\n--- 测试 7: 清空 ---")
        count = await store.clear()
        print(f"清空数量: {count}")

        stats = await store.get_stats()
        print(f"清空后记忆数: {stats.total_count}")

    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)


def test_models():
    """测试数据模型"""
    print("\n测试数据模型...")

    # 创建记忆条目
    entry = MemoryEntry(
        content="test content",
        session_id="session_123",
        message_type=MessageType.KNOWLEDGE,
        source=MemorySource.MANUAL,
        importance=0.9,
        tags=["test"],
    )
    print(f"  ID: {entry.id}")
    print(f"  内容: {entry.content}")
    print(f"  重要性: {entry.importance}")

    # 序列化/反序列化
    data = entry.to_dict()
    restored = MemoryEntry.from_dict(data)
    assert restored.content == entry.content
    print("  序列化/反序列化: OK")

    # 重要性范围限制
    entry_high = MemoryEntry(content="test", importance=1.5)
    assert entry_high.importance == 1.0
    entry_low = MemoryEntry(content="test", importance=-0.5)
    assert entry_low.importance == 0.0
    print("  重要性范围限制: OK")

    print("数据模型测试通过!")


def test_config():
    """测试配置"""
    print("\n测试配置...")

    # 默认配置
    config = LongMemoryConfig()
    assert config.persist_directory == "./data/chroma"
    assert config.default_search_limit == 5
    print("  默认配置: OK")

    # 从字典创建
    config = LongMemoryConfig.from_dict({
        "persist_directory": "/custom/path",
        "default_search_limit": 10,
    })
    assert config.persist_directory == "/custom/path"
    assert config.default_search_limit == 10
    print("  从字典创建: OK")

    # 验证
    errors = config.validate()
    assert len(errors) == 0
    print("  配置验证: OK")

    print("配置测试通过!")


if __name__ == "__main__":
    print("开始测试 long-memory 插件")
    print("=" * 50)

    # 测试配置和模型
    test_config()
    test_models()

    # 测试向量存储
    asyncio.run(test_basic_operations())

    print("\n✅ 所有测试通过!")
