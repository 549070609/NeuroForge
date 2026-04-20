#!/usr/bin/env python3
"""测试命令系统 - 验证所有命令能否正确加载"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pyagentforge.agents.commands import CommandRegistry


def test_commands():
    """测试命令加载"""
    print("=" * 60)
    print("PyAgentForge 命令系统测试")
    print("=" * 60)

    # 创建命令注册表
    registry = CommandRegistry(auto_load=True)

    # 获取所有命令
    commands = registry.get_all_commands()
    command_names = registry.get_command_names()

    print(f"\n✓ 成功加载 {len(command_names)} 个命令\n")

    # 按类别分组
    categories = {}
    for cmd in commands:
        category = cmd.metadata.category or "未分类"
        if category not in categories:
            categories[category] = []
        categories[category].append(cmd)

    # 显示命令列表
    for category, cmds in sorted(categories.items()):
        print(f"\n【{category.upper()}】")
        print("-" * 60)

        for cmd in sorted(cmds, key=lambda c: c.name):
            # 显示命令名称和别名
            aliases = ", ".join(cmd.metadata.alias) if cmd.metadata.alias else ""
            alias_str = f" (别名: {aliases})" if aliases else ""

            print(f"  /{cmd.name}{alias_str}")
            print(f"    {cmd.metadata.description}")

            # 显示需要的工具
            if cmd.metadata.tools:
                tools = ", ".join(cmd.metadata.tools)
                print(f"    工具: {tools}")

    # 测试动态命令注入
    print("\n" + "=" * 60)
    print("测试动态命令注入")
    print("=" * 60)

    test_command = registry.get("status")
    if test_command:
        # 检查是否包含动态命令
        has_dynamic = "!" in test_command.body and "`" in test_command.body
        print(f"\n/status 命令包含动态注入: {'✓ 是' if has_dynamic else '✗ 否'}")

        # 显示命令内容的摘要
        lines = test_command.body.split("\n")
        print(f"命令内容行数: {len(lines)}")

    # 显示别名映射
    print("\n" + "=" * 60)
    print("别名映射")
    print("=" * 60)

    aliases = registry.loader.get_aliases()
    if aliases:
        for alias, cmd_name in sorted(aliases.items()):
            print(f"  /{alias} → /{cmd_name}")
    else:
        print("  无别名")

    # 显示统计信息
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)
    print(f"  总命令数: {len(command_names)}")
    print(f"  总别名数: {len(aliases)}")
    print(f"  分类数: {len(categories)}")

    # 检查加载错误
    errors = registry.loader.get_load_errors()
    if errors:
        print("\n" + "=" * 60)
        print("⚠️  加载错误")
        print("=" * 60)
        for path, error in errors.items():
            print(f"  {path}: {error}")
    else:
        print("\n✓ 所有命令加载成功，无错误")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_commands()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
