#!/usr/bin/env python
"""
快速运行脚本

快速测试小说创作系统的各个组件
"""

import sys
from pathlib import Path

# 添加 pyagentforge 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "main" / "pyagentforge"))


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("📚 小说创作多 Agent 系统 - 快速测试")
    print("=" * 70 + "\n")

    print("可用命令：\n")
    print("  1. python builder_demo.py     - 测试 AgentBuilder")
    print("  2. python loader_demo.py      - 测试 AgentLoader")
    print("  3. python workflow_demo.py    - 测试完整工作流")
    print()

    choice = input("请选择要运行的演示 (1-3): ").strip()

    if choice == "1":
        print("\n运行 Builder 演示...\n")
        import builder_demo

        builder_demo.demo_builder_features()

    elif choice == "2":
        print("\n运行 Loader 演示...\n")
        import loader_demo

        loader_demo.main()

    elif choice == "3":
        print("\n运行工作流演示...\n")
        import workflow_demo

        workflow_demo.demo_workflow()

    else:
        print("\n❌ 无效选择")
        return

    print("\n✅ 演示完成\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback

        traceback.print_exc()
