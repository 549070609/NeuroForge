"""
Local Embeddings 单元测试
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from embeddings_provider import EmbeddingsProvider


async def test_basic_embed():
    """测试基本嵌入功能"""
    print("测试 1: 基本嵌入生成")

    provider = EmbeddingsProvider(model_name="all-MiniLM-L6-v2")
    texts = ["Hello world", "Test embedding", "机器学习很有趣"]

    embeddings = await provider.embed(texts)

    assert len(embeddings) == 3, f"期望 3 个向量，得到 {len(embeddings)}"
    assert len(embeddings[0]) == 384, f"期望 384 维，得到 {len(embeddings[0])}"

    print(f"  ✓ 生成了 {len(embeddings)} 个嵌入向量")
    print(f"  ✓ 每个向量维度: {len(embeddings[0])}")
    print()

    return True


async def test_empty_input():
    """测试空输入"""
    print("测试 2: 空输入处理")

    provider = EmbeddingsProvider(model_name="all-MiniLM-L6-v2")
    embeddings = await provider.embed([])

    assert embeddings == [], "空输入应返回空列表"

    print("  ✓ 空输入正确处理")
    print()

    return True


async def test_batch_processing():
    """测试批处理"""
    print("测试 3: 批处理 (batch_size=4)")

    provider = EmbeddingsProvider(model_name="all-MiniLM-L6-v2", max_batch_size=4)

    # 10 条文本，应该分成 3 批
    texts = [f"Text number {i}" for i in range(10)]
    embeddings = await provider.embed(texts)

    assert len(embeddings) == 10, f"期望 10 个向量，得到 {len(embeddings)}"

    print(f"  ✓ 正确处理 10 条文本")
    print()

    return True


async def test_normalization():
    """测试向量归一化"""
    print("测试 4: 向量归一化")

    provider = EmbeddingsProvider(model_name="all-MiniLM-L6-v2")
    texts = ["Test normalization"]

    embeddings = await provider.embed(texts)

    # 计算向量 L2 范数
    import numpy as np

    vec = np.array(embeddings[0])
    norm = np.linalg.norm(vec)

    assert abs(norm - 1.0) < 0.01, f"L2 范数应接近 1.0，得到 {norm}"

    print(f"  ✓ 向量 L2 范数: {norm:.6f} (接近 1.0)")
    print()

    return True


async def test_similarity():
    """测试语义相似度"""
    print("测试 5: 语义相似度计算")

    provider = EmbeddingsProvider(model_name="all-MiniLM-L6-v2")

    texts = [
        "The cat sat on the mat",
        "A cat is sitting on a carpet",
        "The stock market crashed today",
    ]

    embeddings = await provider.embed(texts)

    # 计算相似度
    import numpy as np

    vec1 = np.array(embeddings[0])
    vec2 = np.array(embeddings[1])
    vec3 = np.array(embeddings[2])

    sim_1_2 = np.dot(vec1, vec2)  # 两个猫相关的句子
    sim_1_3 = np.dot(vec1, vec3)  # 猫和股票市场

    print(f"  'cat on mat' vs 'cat on carpet': {sim_1_2:.4f}")
    print(f"  'cat on mat' vs 'stock market': {sim_1_3:.4f}")

    assert sim_1_2 > sim_1_3, "相似句子应有更高相似度"

    print("  ✓ 语义相似度计算正确")
    print()

    return True


async def test_local_model():
    """测试本地模型加载"""
    print("测试 6: 本地模型加载")

    model_path = Path(__file__).parent / "models" / "all-MiniLM-L6-v2"

    if not model_path.exists():
        print("  ⊘ 跳过: 本地模型不存在")
        print()
        return True

    provider = EmbeddingsProvider(model_path=str(model_path))
    texts = ["Testing local model"]

    embeddings = await provider.embed(texts)

    assert len(embeddings) == 1, "应该生成 1 个向量"
    assert len(embeddings[0]) == 384, "维度应为 384"

    print(f"  ✓ 本地模型加载成功")
    print()

    return True


async def test_sync_method():
    """测试同步方法"""
    print("测试 7: 同步嵌入方法")

    provider = EmbeddingsProvider(model_name="all-MiniLM-L6-v2")
    texts = ["Sync test"]

    embeddings = provider.embed_sync(texts)

    assert len(embeddings) == 1, "应该生成 1 个向量"

    print("  ✓ 同步方法工作正常")
    print()

    return True


async def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("Local Embeddings 测试套件")
    print("=" * 50)
    print()

    tests = [
        test_basic_embed,
        test_empty_input,
        test_batch_processing,
        test_normalization,
        test_similarity,
        test_local_model,
        test_sync_method,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append((test.__name__, result, None))
        except Exception as e:
            results.append((test.__name__, False, str(e)))
            print(f"  ✗ 测试失败: {e}")
            print()

    # 汇总结果
    print("=" * 50)
    print("测试结果汇总")
    print("=" * 50)

    passed = sum(1 for _, r, _ in results if r)
    total = len(results)

    for name, result, error in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status}: {name}")
        if error:
            print(f"    错误: {error}")

    print()
    print(f"总计: {passed}/{total} 测试通过")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
