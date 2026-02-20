#!/usr/bin/env python
"""
AGent 启动脚本 - 快速选择模式
"""

import sys
import subprocess
from pathlib import Path


# Windows 上使用 py 命令
PYTHON_CMD = "py" if sys.platform == "win32" else "python"


def main():
    print("\n" + "="*60)
    print("📚 AGent - 小说创作多 Agent 系统")
    print("="*60 + "\n")

    print("选择启动模式：\n")
    print("  1. GLM AI 模式（推荐，中文优化）")
    print("  2. Mock 模式（测试 UI，无需 API Key）")
    print("  3. 真实 AI 模式（Anthropic Claude）")
    print("  4. 配置 GLM API Key")
    print("  5. 查看使用说明")
    print("  6. 退出\n")

    choice = input("请选择 (1-6): ").strip()

    if choice == "1":
        print("\n🚀 启动 GLM AI 模式...\n")

        # 检查配置
        env_file = Path(__file__).parent.parent / "glm-provider" / ".env"
        if not env_file.exists():
            print("⚠️  未找到 GLM 配置文件！")
            print("   请先运行：py setup_glm.py")
            print("   或选择菜单 4 配置 GLM API Key\n")
            return

        subprocess.run([PYTHON_CMD, "cli_glm.py"])

    elif choice == "2":
        print("\n🚀 启动 Mock 模式...\n")
        subprocess.run([PYTHON_CMD, "cli_real.py"])

    elif choice == "3":
        print("\n🚀 启动 Anthropic AI 模式...\n")

        # 检查 .env 文件
        env_file = Path(__file__).parent.parent / "pyagentforge" / ".env"
        if not env_file.exists():
            print("⚠️  未找到 .env 文件！")
            print(f"   请在 {env_file.parent} 创建 .env 文件")
            print("   并添加：ANTHROPIC_API_KEY=your_key_here\n")
            return

        subprocess.run([PYTHON_CMD, "cli_real.py", "--real"])

    elif choice == "4":
        print("\n🔧 启动 GLM 配置向导...\n")
        subprocess.run([PYTHON_CMD, "setup_glm.py"])

    elif choice == "5":
        print("\n📖 打开使用说明...\n")
        readme = Path(__file__).parent / "README_GLM.md"
        if readme.exists():
            with open(readme, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            print("❌ 未找到 README_GLM.md")

    elif choice == "6":
        print("\n👋 再见！\n")
        return

    else:
        print("\n❌ 无效选择\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
