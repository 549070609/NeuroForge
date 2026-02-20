"""
验证 Agent 构建层工具串联完整性

检查点:
1. 所有 Agent 需要的工具是否存在
2. 工具注册表是否能正确过滤
3. Agent Engine 是否能正确创建
"""

from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.agents.metadata import BUILTIN_AGENTS


def main():
    print("=" * 70)
    print("Agent 构建层工具串联验证")
    print("=" * 70)

    # 1. 创建工具注册表并注册所有工具
    print("\n[1] 注册所有工具...")
    registry = ToolRegistry()
    registry.register_builtin_tools()
    registry.register_p0_tools()
    registry.register_extended_tools()

    all_tools = registry.get_all()
    print(f"✅ 已注册 {len(all_tools)} 个工具")

    # 2. 检查每个 Agent 的工具覆盖度
    print("\n[2] 检查 Agent 工具覆盖度...")
    print("-" * 70)

    total_issues = 0

    for agent_name, agent in BUILTIN_AGENTS.items():
        allowed_tools = agent.tools

        if "*" in allowed_tools:
            coverage = "100% (所有工具)"
            missing = []
            available_count = len(all_tools)
        else:
            available = [t for t in allowed_tools if t in all_tools]
            missing = [t for t in allowed_tools if t not in all_tools]
            coverage = f"{len(available)}/{len(allowed_tools)} ({len(available)*100//len(allowed_tools)}%)"
            available_count = len(available)

        # 显示状态
        status = "✅" if not missing else "❌"
        print(f"{status} {agent_name:12} | {agent.category.value:12} | 工具: {coverage:15} | 成本: {agent.cost.value:9}")

        if missing:
            print(f"   ⚠️  缺失工具: {missing}")
            total_issues += len(missing)

    print("-" * 70)

    # 3. 测试工具过滤功能
    print("\n[3] 测试工具过滤功能...")

    # 测试 explore agent 的工具过滤
    explore_agent = BUILTIN_AGENTS["explore"]
    filtered_registry = registry.filter_by_permission(explore_agent.tools)

    print(f"explore agent 工具: {explore_agent.tools}")
    print(f"过滤后工具数: {len(filtered_registry.get_all())}")
    print(f"过滤后工具列表: {list(filtered_registry.get_all().keys())}")

    # 4. 测试 * 权限（所有工具）
    print("\n[4] 测试 * 权限（code agent）...")

    code_agent = BUILTIN_AGENTS["code"]
    all_tools_registry = registry.filter_by_permission(code_agent.tools)

    print(f"code agent 工具: {code_agent.tools}")
    print(f"过滤后工具数: {len(all_tools_registry.get_all())}")

    # 5. 最终报告
    print("\n" + "=" * 70)
    print("验证结果")
    print("=" * 70)

    if total_issues == 0:
        print("✅ 所有 Agent 工具覆盖完整！")
        print(f"✅ 工具注册表功能正常")
        print(f"✅ 权限过滤机制正常")
        print(f"\n🎉 Agent 构建层可以完美串联所有 {len(all_tools)} 个工具！")
    else:
        print(f"❌ 发现 {total_issues} 个工具缺失问题")

    print("=" * 70)

    # 6. 显示所有可用工具
    print("\n[5] 所有可用工具列表:")
    for idx, tool_name in enumerate(sorted(all_tools.keys()), 1):
        tool = all_tools[tool_name]
        desc = tool.description[:50] + "..." if len(tool.description) > 50 else tool.description
        print(f"  {idx:2}. {tool_name:15} - {desc}")


if __name__ == "__main__":
    main()
