#!/usr/bin/env python3
"""
思维链系统验证脚本

验证修复后的导入和基本功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_import():
    """测试导入"""
    print("=" * 60)
    print("测试 1: 导入 ChainOfThoughtPlugin")
    print("=" * 60)

    try:
        from pyagentforge.plugins.integration.chain_of_thought.PLUGIN import ChainOfThoughtPlugin
        print("✅ 导入成功")
        print(f"   类名: {ChainOfThoughtPlugin.__name__}")
        print(f"   基类: {ChainOfThoughtPlugin.__bases__}")
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_plugin_metadata():
    """测试插件元数据"""
    print("\n" + "=" * 60)
    print("测试 2: 插件元数据")
    print("=" * 60)

    try:
        from pyagentforge.plugins.integration.chain_of_thought.PLUGIN import ChainOfThoughtPlugin
        plugin = ChainOfThoughtPlugin()

        print(f"   ID: {plugin.metadata.id}")
        print(f"   名称: {plugin.metadata.name}")
        print(f"   版本: {plugin.metadata.version}")
        print(f"   类型: {plugin.metadata.type}")
        print(f"   优先级: {plugin.metadata.priority}")
        print("✅ 元数据创建成功")
        return True
    except Exception as e:
        print(f"❌ 元数据创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tools_registration():
    """测试工具注册"""
    print("\n" + "=" * 60)
    print("测试 3: 工具注册")
    print("=" * 60)

    try:
        from pyagentforge.plugins.integration.chain_of_thought.PLUGIN import ChainOfThoughtPlugin
        plugin = ChainOfThoughtPlugin()

        # 模拟激活
        import asyncio
        asyncio.run(plugin.on_activate())

        tools = plugin.get_tools()
        print(f"   已注册工具数: {len(tools)}")

        # 列出所有工具
        tool_names = [tool.name for tool in tools]
        print(f"   工具列表: {', '.join(tool_names)}")

        # 验证工具数量
        expected_count = 16  # 5 基础 + 4 Phase 3 + 7 Phase 4
        if len(tools) == expected_count:
            print(f"✅ 工具注册正确（{expected_count} 个）")
            return True
        else:
            print(f"⚠️  工具数量不匹配（预期 {expected_count}，实际 {len(tools)}）")
            return False
    except Exception as e:
        print(f"❌ 工具注册失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hooks_implementation():
    """测试钩子实现"""
    print("\n" + "=" * 60)
    print("测试 4: 钩子实现")
    print("=" * 60)

    try:
        from pyagentforge.plugins.integration.chain_of_thought.PLUGIN import ChainOfThoughtPlugin
        plugin = ChainOfThoughtPlugin()

        hooks = plugin.get_hooks()
        print(f"   已实现钩子数: {len(hooks)}")

        # 列出所有钩子
        hook_names = list(hooks.keys())
        print(f"   钩子列表: {', '.join(hook_names)}")

        # 验证关键钩子
        required_hooks = [
            "on_engine_start",
            "on_engine_stop",
            "on_before_llm_call",
            "on_before_tool_call",
            "on_after_tool_call",
            "on_task_complete",
        ]

        missing_hooks = [h for h in required_hooks if h not in hooks]
        if not missing_hooks:
            print(f"✅ 所有关键钩子已实现")
            return True
        else:
            print(f"⚠️  缺少钩子: {', '.join(missing_hooks)}")
            return False
    except Exception as e:
        print(f"❌ 钩子检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manager_import():
    """测试管理器导入"""
    print("\n" + "=" * 60)
    print("测试 5: ChainOfThoughtManager 导入")
    print("=" * 60)

    try:
        from pyagentforge.plugins.integration.chain_of_thought.cot_manager import ChainOfThoughtManager
        print("✅ ChainOfThoughtManager 导入成功")
        return True
    except Exception as e:
        print(f"❌ ChainOfThoughtManager 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_models_import():
    """测试模型导入"""
    print("\n" + "=" * 60)
    print("测试 6: 数据模型导入")
    print("=" * 60)

    try:
        from pyagentforge.plugins.integration.chain_of_thought.models import (
            Phase,
            Constraint,
            ConstraintType,
            Reflection,
            ChainOfThought,
        )
        print("✅ 数据模型导入成功")
        print(f"   模型: Phase, Constraint, ConstraintType, Reflection, ChainOfThought")
        return True
    except Exception as e:
        print(f"❌ 数据模型导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("思维链系统验证脚本")
    print("=" * 60)

    tests = [
        test_import,
        test_plugin_metadata,
        test_tools_registration,
        test_hooks_implementation,
        test_manager_import,
        test_models_import,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ 测试执行异常: {e}")
            results.append(False)

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"通过: {passed}/{total}")

    if passed == total:
        print("\n✅ 所有测试通过！")
        print("\n下一步:")
        print("  1. 运行完整测试套件:")
        print("     python -m pytest pyagentforge/plugins/integration/chain_of_thought/tests/ -v")
        print("  2. 检查测试覆盖率:")
        print("     python -m pytest pyagentforge/plugins/integration/chain_of_thought/tests/ --cov --cov-report=term-missing")
        return 0
    else:
        print(f"\n❌ {total - passed} 个测试失败")
        print("\n请检查以上错误信息并修复问题。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
