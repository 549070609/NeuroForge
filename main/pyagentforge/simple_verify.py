"""简单的工具覆盖验证"""

# 手动检查所有工具
print("=== Agent 工具覆盖验证 ===\n")

# 已知工具列表（从 tools/builtin/ 目录）
available_tools = {
    # Builtin (P0)
    "bash", "read", "write", "edit", "glob", "grep",
    # P0
    "ls", "lsp", "question", "confirm",
    # P1
    "codesearch", "apply_patch", "diff", "plan",
    # P2
    "truncation", "compact", "invalid", "tool_suggestion", "external_directory", "workspace",
    # Extended
    "webfetch", "websearch", "multiedit", "todo_write", "todo_read",
    # Task
    "task"
}

# Agent 工具需求
agent_tools = {
    "explore": ["bash", "read", "glob", "grep"],
    "plan": ["bash", "read", "glob", "grep"],
    "code": ["*"],  # 所有工具
    "review": ["bash", "read", "glob", "grep"],
    "librarian": ["webfetch", "read"],
    "oracle": ["bash", "read", "glob", "grep"],
}

print(f"总工具数: {len(available_tools)}\n")

all_ok = True
for agent_name, tools in agent_tools.items():
    if "*" in tools:
        print(f"✅ {agent_name:12} - 所有工具 ({len(available_tools)} 个)")
    else:
        missing = [t for t in tools if t not in available_tools]
        if missing:
            print(f"❌ {agent_name:12} - 缺失: {missing}")
            all_ok = False
        else:
            print(f"✅ {agent_name:12} - {len(tools)}/{len(tools)} 工具可用")

print("\n" + "=" * 50)
if all_ok:
    print("🎉 所有 Agent 工具覆盖完整！")
else:
    print("❌ 存在工具缺失")
