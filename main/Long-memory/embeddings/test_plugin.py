"""
Local Embeddings 插件集成测试

验证插件能否被 pyagentforge 正确加载和使用
"""

import asyncio
import sys
from pathlib import Path

# 添加 pyagentforge 路径
pyagentforge_path = Path(__file__).parent.parent.parent / "pyagentforge"
if pyagentforge_path.exists():
    sys.path.insert(0, str(pyagentforge_path.parent))

# 添加本插件路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_plugin_discovery():
    """测试插件发现"""
    print("测试 1: 插件发现")

    from pyagentforge.plugin.loader import PluginLoader
    from pyagentforge.plugin.registry import PluginRegistry
    from pyagentforge.plugin.dependencies import DependencyResolver

    registry = PluginRegistry()
    resolver = DependencyResolver()
    loader = PluginLoader(registry, resolver)

    plugin_dirs = [str(Path(__file__).parent.parent)]
    discovered = loader.discover(plugin_dirs)

    print(f"  发现的插件目录: {discovered}")

    assert len(discovered) > 0, "应该发现至少一个插件"

    print("  ✓ 插件发现成功")
    print()

    return True


async def test_plugin_loading():
    """测试插件加载"""
    print("测试 2: 插件加载")

    from pyagentforge.plugin.loader import PluginLoader
    from pyagentforge.plugin.registry import PluginRegistry
    from pyagentforge.plugin.dependencies import DependencyResolver

    registry = PluginRegistry()
    resolver = DependencyResolver()
    loader = PluginLoader(registry, resolver)

    plugin_path = str(Path(__file__).parent.parent)
    plugin = loader.load(plugin_path)

    print(f"  插件 ID: {plugin.metadata.id}")
    print(f"  插件名称: {plugin.metadata.name}")
    print(f"  插件版本: {plugin.metadata.version}")
    print(f"  插件类型: {plugin.metadata.type}")

    assert plugin.metadata.id == "tool.local-embeddings", "插件 ID 不正确"
    assert plugin.metadata.name == "Local Embeddings", "插件名称不正确"

    print("  ✓ 插件加载成功")
    print()

    return True


async def test_plugin_tools():
    """测试插件工具"""
    print("测试 3: 插件工具")

    from pyagentforge.plugin.loader import PluginLoader
    from pyagentforge.plugin.registry import PluginRegistry
    from pyagentforge.plugin.dependencies import DependencyResolver
    from pyagentforge.plugin.base import PluginContext

    registry = PluginRegistry()
    resolver = DependencyResolver()
    loader = PluginLoader(registry, resolver)

    plugin_path = str(Path(__file__).parent.parent)
    plugin = loader.load(plugin_path)

    # 模拟上下文
    class MockLogger:
        def info(self, msg):
            print(f"  [INFO] {msg}")

        def warning(self, msg):
            print(f"  [WARN] {msg}")

        def error(self, msg):
            print(f"  [ERROR] {msg}")

    class MockEngine:
        pass

    context = PluginContext(
        engine=MockEngine(),
        config={"device": "cpu"},
        logger=MockLogger(),
    )

    # 加载和激活插件
    await plugin.on_plugin_load(context)
    await plugin.on_plugin_activate()

    # 获取工具
    tools = plugin.get_tools()

    print(f"  提供的工具数量: {len(tools)}")
    for tool in tools:
        print(f"    - {tool.name}: {tool.description}")

    assert len(tools) == 2, "应该提供 2 个工具"

    tool_names = [t.name for t in tools]
    assert "embed_text" in tool_names, "应该有 embed_text 工具"
    assert "compute_similarity" in tool_names, "应该有 compute_similarity 工具"

    print("  ✓ 工具检查通过")
    print()

    return True


async def test_tool_execution():
    """测试工具执行"""
    print("测试 4: 工具执行")

    from pyagentforge.plugin.loader import PluginLoader
    from pyagentforge.plugin.registry import PluginRegistry
    from pyagentforge.plugin.dependencies import DependencyResolver
    from pyagentforge.plugin.base import PluginContext

    registry = PluginRegistry()
    resolver = DependencyResolver()
    loader = PluginLoader(registry, resolver)

    plugin_path = str(Path(__file__).parent.parent)
    plugin = loader.load(plugin_path)

    # 模拟上下文
    class MockLogger:
        def info(self, msg):
            pass

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

    # 加载和激活插件
    await plugin.on_plugin_load(context)
    await plugin.on_plugin_activate()

    # 获取工具
    tools = plugin.get_tools()
    tools_dict = {t.name: t for t in tools}

    # 测试 embed_text
    print("  测试 embed_text 工具:")
    embed_tool = tools_dict["embed_text"]
    result = await embed_tool.execute(["Hello world", "测试文本"])
    print(f"    结果: {result[:50]}...")

    assert "成功" in result or "错误" not in result, "embed_text 应该成功"

    # 测试 compute_similarity
    print("  测试 compute_similarity 工具:")
    sim_tool = tools_dict["compute_similarity"]
    result = await sim_tool.execute("猫是宠物", "狗是家养动物")
    print(f"    结果: {result}")

    assert "相似度" in result, "compute_similarity 应返回相似度"

    print("  ✓ 工具执行成功")
    print()

    return True


async def test_full_integration():
    """测试完整集成（如果 pyagentforge 可用）"""
    print("测试 5: 完整集成测试")

    try:
        from pyagentforge import create_engine, PluginConfig
        from pyagentforge.providers import AnthropicProvider
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("  ⊘ 跳过: 未设置 ANTHROPIC_API_KEY")
            print()
            return True

        plugin_config = PluginConfig(
            preset="minimal",
            enabled=["tool.local-embeddings"],
            plugin_dirs=[str(Path(__file__).parent.parent)],
            config={"tool.local-embeddings": {"device": "cpu"}},
        )

        engine = await create_engine(
            provider=AnthropicProvider(api_key=api_key),
            plugin_config=plugin_config,
        )

        # 检查工具是否注册
        tool_names = [t.name for t in engine.tools]
        print(f"  已注册工具: {tool_names}")

        assert "embed_text" in tool_names, "embed_text 应该被注册"
        assert "compute_similarity" in tool_names, "compute_similarity 应该被注册"

        print("  ✓ 完整集成测试通过")
        print()

        return True

    except ImportError as e:
        print(f"  ⊘ 跳过: pyagentforge 不可用 ({e})")
        print()
        return True
    except Exception as e:
        print(f"  ✗ 测试失败: {e}")
        print()
        return False


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("Local Embeddings 插件集成测试")
    print("=" * 60)
    print()

    tests = [
        test_plugin_discovery,
        test_plugin_loading,
        test_plugin_tools,
        test_tool_execution,
        test_full_integration,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append((test.__name__, result, None))
        except Exception as e:
            results.append((test.__name__, False, str(e)))
            print(f"  ✗ 测试失败: {e}")
            import traceback

            traceback.print_exc()
            print()

    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)

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
