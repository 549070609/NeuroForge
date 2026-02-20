"""
Local Embeddings 使用示例

展示如何在 pyagentforge 中使用 Local Embeddings 插件
"""

import asyncio
import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "pyagentforge"))


async def example_standalone():
    """独立使用 EmbeddingsProvider"""
    print("=" * 60)
    print("示例 1: 独立使用 EmbeddingsProvider")
    print("=" * 60)
    print()

    from embeddings_provider import EmbeddingsProvider

    # 创建提供者
    provider = EmbeddingsProvider(
        model_name="all-MiniLM-L6-v2",
        device="cpu",
    )

    # 生成嵌入
    texts = [
        "Python 是一种流行的编程语言",
        "JavaScript 是网页开发的核心语言",
        "机器学习正在改变各行各业",
    ]

    print(f"输入文本 ({len(texts)} 条):")
    for i, text in enumerate(texts, 1):
        print(f"  {i}. {text}")
    print()

    embeddings = await provider.embed(texts)

    print(f"生成嵌入向量:")
    print(f"  数量: {len(embeddings)}")
    print(f"  维度: {len(embeddings[0])}")
    print()

    # 计算相似度
    import numpy as np

    vec1 = np.array(embeddings[0])
    vec2 = np.array(embeddings[1])
    vec3 = np.array(embeddings[2])

    print("语义相似度分析:")
    print(f"  Python vs JavaScript: {np.dot(vec1, vec2):.4f}")
    print(f"  Python vs 机器学习: {np.dot(vec1, vec3):.4f}")
    print(f"  JavaScript vs 机器学习: {np.dot(vec2, vec3):.4f}")
    print()


async def example_with_tools():
    """使用插件工具"""
    print("=" * 60)
    print("示例 2: 使用插件工具")
    print("=" * 60)
    print()

    from pyagentforge.plugin.loader import PluginLoader
    from pyagentforge.plugin.registry import PluginRegistry
    from pyagentforge.plugin.dependencies import DependencyResolver
    from pyagentforge.plugin.base import PluginContext

    # 加载插件
    registry = PluginRegistry()
    resolver = DependencyResolver()
    loader = PluginLoader(registry, resolver)

    plugin_path = str(Path(__file__).parent.parent)
    plugin = loader.load(plugin_path)

    # 创建模拟上下文
    class MockLogger:
        def info(self, msg):
            print(f"  [INFO] {msg}")

        def warning(self, msg):
            pass

        def error(self, msg):
            pass

    class MockEngine:
        pass

    context = PluginContext(
        engine=MockEngine(),
        config={"device": "cpu"},
        logger=MockLogger(),
    )

    # 激活插件
    await plugin.on_plugin_load(context)
    await plugin.on_plugin_activate()

    # 获取工具
    tools = {t.name: t for t in plugin.get_tools()}

    # 使用 embed_text 工具
    print("使用 embed_text 工具:")
    result = await tools["embed_text"].execute(
        ["人工智能正在快速发展", "深度学习是 AI 的核心技术"]
    )
    print(f"  结果: {result}")
    print()

    # 使用 compute_similarity 工具
    print("使用 compute_similarity 工具:")
    result = await tools["compute_similarity"].execute(
        "猫是一种常见的宠物", "狗是人类最好的朋友"
    )
    print(f"  结果: {result}")
    print()


async def example_with_engine():
    """在完整 engine 中使用（需要 API key）"""
    print("=" * 60)
    print("示例 3: 在 Agent Engine 中使用")
    print("=" * 60)
    print()

    import os

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  跳过: 需要设置 ANTHROPIC_API_KEY 环境变量")
        print("  示例命令:")
        print('    $env:ANTHROPIC_API_KEY="your-key-here"')
        print("    python examples.py")
        print()
        return

    try:
        from pyagentforge import create_engine, PluginConfig
        from pyagentforge.providers import AnthropicProvider

        plugin_config = PluginConfig(
            preset="minimal",
            enabled=["tool.local-embeddings"],
            plugin_dirs=[str(Path(__file__).parent.parent)],
            config={"tool.local-embeddings": {"device": "cpu"}},
        )

        print("  创建 Agent Engine...")
        engine = await create_engine(
            provider=AnthropicProvider(api_key=api_key),
            plugin_config=plugin_config,
        )

        print(f"  已加载工具: {[t.name for t in engine.tools]}")
        print()

        # 使用 Agent 计算相似度
        print("  请求 Agent 计算语义相似度...")
        result = await engine.run(
            "请计算 '今天天气很好' 和 '今天是晴朗的一天' 的语义相似度"
        )
        print(f"  结果: {result}")
        print()

    except ImportError as e:
        print(f"  跳过: pyagentforge 不可用 ({e})")
        print()


async def main():
    """运行所有示例"""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       Local Embeddings 使用示例                           ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    await example_standalone()
    await example_with_tools()
    await example_with_engine()

    print("=" * 60)
    print("示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
