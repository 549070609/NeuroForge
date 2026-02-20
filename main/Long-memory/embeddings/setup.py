#!/usr/bin/env python3
"""
Local Embeddings 安装脚本

自动安装依赖并验证安装
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """运行命令并显示进度"""
    print(f"\n{'=' * 60}")
    print(f"{description}...")
    print(f"{'=' * 60}")
    print(f"命令: {cmd}")
    print()

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            cwd=Path(__file__).parent,
        )
        print(f"\n✓ {description} 成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {description} 失败")
        print(f"错误: {e}")
        return False


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"\nPython 版本: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("✗ 需要 Python 3.8 或更高版本")
        return False

    print("✓ Python 版本符合要求")
    return True


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       Local Embeddings 安装向导                           ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # 检查 Python 版本
    if not check_python_version():
        sys.exit(1)

    # 安装依赖
    if not run_command(
        f'"{sys.executable}" -m pip install -r requirements.txt',
        "安装依赖包",
    ):
        print("\n提示: 如果 pip 安装失败，请尝试:")
        print("  pip install --upgrade pip")
        print("  pip install -r requirements.txt --user")
        sys.exit(1)

    # 运行测试
    print("\n" + "=" * 60)
    print("是否运行测试以验证安装? (推荐)")
    print("=" * 60)
    response = input("输入 y 继续，其他键跳过: ").strip().lower()

    if response == "y":
        if not run_command(
            f'"{sys.executable}" test_embeddings.py',
            "运行单元测试",
        ):
            print("\n警告: 测试失败，但依赖已安装")
            print("可能的原因:")
            print("  - 首次运行需要下载模型（网络连接）")
            print("  - 内存不足")
            print("\n请检查上面的错误信息")
        else:
            print("\n" + "🎉 " * 20)
            print("安装成功！")
            print("🎉 " * 20)

    # 显示后续步骤
    print("\n" + "=" * 60)
    print("后续步骤")
    print("=" * 60)
    print("\n1. 查看快速启动指南:")
    print("   cat QUICKSTART.md")
    print("\n2. 运行示例:")
    print("   python examples.py")
    print("\n3. 在 pyagentforge 中使用:")
    print("   参考 README.md 中的集成说明")
    print("\n4. 查看完整文档:")
    print("   cat README.md")
    print()


if __name__ == "__main__":
    main()
