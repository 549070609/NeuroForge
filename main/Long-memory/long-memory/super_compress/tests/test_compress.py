"""
超级压缩插件测试
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pyagentforge.plugins.integration.super_compress import (
    TokenBudgetManager,
    SummaryGenerator,
)
from pyagentforge.plugins.integration.super_compress.summary_generator import (
    SummaryStrategy,
)


def create_test_messages(count: int = 100) -> list:
    """创建测试消息"""
    messages = []

    for i in range(count):
        # 用户消息
        messages.append({
            "role": "user",
            "content": f"这是第 {i+1} 条用户消息。我正在询问关于 Python 编程的问题，"
            f"特别是关于异步编程和并发处理的内容。这是一个较长的消息，"
            f"用于模拟真实的对话场景。",
        })

        # 助手消息
        messages.append({
            "role": "assistant",
            "content": f"这是对第 {i+1} 个问题的回答。Python 的异步编程主要使用 asyncio 库，"
            f"它提供了 async/await 语法来编写异步代码。关键概念包括协程、"
            f"事件循环和任务。在实际应用中，异步编程可以提高 I/O 密集型应用的性能。",
        })

    return messages


def test_budget_manager():
    """测试预算管理器"""
    print("=" * 50)
    print("测试 Token 预算管理器")
    print("=" * 50)

    manager = TokenBudgetManager(
        model="claude-3-sonnet",
        compress_threshold=0.8,
    )

    print(f"\n模型: {manager.model}")
    print(f"上下文限制: {manager.context_limit:,} tokens")
    print(f"压缩阈值: {manager.compress_threshold:.0%}")

    # 测试不同数量的消息
    for msg_count in [10, 50, 100, 200]:
        messages = create_test_messages(msg_count)
        budget = manager.calculate(messages)

        print(f"\n{msg_count} 条消息 ({msg_count * 2} 轮对话):")
        print(f"  - 使用 tokens: {budget.used_tokens:,}")
        print(f"  - 可用 tokens: {budget.available_tokens:,}")
        print(f"  - 使用比例: {budget.compression_ratio:.2%}")
        print(f"  - 需要压缩: {'是' if manager.should_compress(messages) else '否'}")

    print("\n" + "=" * 50)


async def test_summary_generator():
    """测试摘要生成器"""
    print("\n" + "=" * 50)
    print("测试摘要生成器")
    print("=" * 50)

    generator = SummaryGenerator(
        llm_client=None,  # 不使用 LLM
        default_strategy=SummaryStrategy.EXTRACT,
    )

    messages = create_test_messages(30)

    # 测试不同策略
    for strategy in [SummaryStrategy.EXTRACT, SummaryStrategy.SMART]:
        print(f"\n策略: {strategy.value}")

        result = await generator.generate(
            messages=messages,
            strategy=strategy,
            context="Python 异步编程讨论",
        )

        print(f"  - 原始 tokens: {result.original_tokens}")
        print(f"  - 摘要 tokens: {result.summary_tokens}")
        print(f"  - 压缩比: {result.compression_ratio:.2%}")
        print(f"  - 关键点数量: {len(result.key_points)}")
        print(f"\n  摘要内容 (前 300 字符):")
        print(f"  {result.content[:300]}...")


async def test_compression_workflow():
    """测试完整压缩流程"""
    print("\n" + "=" * 50)
    print("测试完整压缩流程")
    print("=" * 50)

    from pyagentforge.plugins.integration.super_compress import CompressEngine

    # 创建组件
    budget_manager = TokenBudgetManager(
        model="claude-3-sonnet",
        compress_threshold=0.3,  # 设置较低的阈值以触发压缩
    )
    summary_generator = SummaryGenerator(
        llm_client=None,
        default_strategy=SummaryStrategy.EXTRACT,
    )
    compress_engine = CompressEngine(
        budget_manager=budget_manager,
        summary_generator=summary_generator,
        long_memory_plugin=None,  # 不使用长记忆
        keep_recent=10,
    )

    # 创建大量消息
    messages = create_test_messages(50)

    print(f"\n原始消息数: {len(messages)}")
    budget = budget_manager.calculate(messages)
    print(f"原始 tokens: {budget.used_tokens:,}")
    print(f"使用比例: {budget.compression_ratio:.2%}")

    # 执行压缩
    result = await compress_engine.compress(
        messages=messages,
        force=False,
        store_to_memory=False,
    )

    print(f"\n压缩后消息数: {len(result.compressed_messages)}")
    print(f"压缩后 tokens: {result.compressed_tokens:,}")
    print(f"最终压缩比: {result.compression_ratio:.2%}")
    print(f"节省 tokens: {result.original_tokens - result.compressed_tokens:,}")

    # 显示压缩预览
    preview = compress_engine.get_compress_preview(messages)
    print(f"\n压缩预览:")
    print(f"  - 需要压缩: {preview['should_compress']}")
    print(f"  - 待压缩消息: {preview['split']['to_compress']}")
    print(f"  - 保留消息: {preview['split']['to_keep']}")


if __name__ == "__main__":
    test_budget_manager()
    asyncio.run(test_summary_generator())
    asyncio.run(test_compression_workflow())
