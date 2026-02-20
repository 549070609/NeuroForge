#!/usr/bin/env python
"""
GLM 配置向导
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def main():
    print("\n" + "="*60)
    print("🔧 GLM Provider 配置向导")
    print("="*60 + "\n")

    # 检查 .env 文件
    env_path = Path(__file__).parent.parent / "glm-provider" / ".env"
    env_example = env_path.parent / ".env.example"

    print(f"配置文件路径：{env_path}\n")

    if env_path.exists():
        print("✅ 找到配置文件\n")
        load_dotenv(env_path)

        # 显示当前配置
        api_key = os.environ.get("GLM_API_KEY", "")
        model = os.environ.get("GLM_MODEL", "glm-4-flash")

        print("当前配置：")
        print(f"  GLM_API_KEY: {api_key[:20]}...{api_key[-10:] if len(api_key) > 30 else '(未设置)'}")
        print(f"  GLM_MODEL: {model}\n")

        choice = input("是否要修改配置？(y/n): ").strip().lower()
        if choice != 'y':
            print("\n✅ 配置未修改")
            return

    else:
        print("❌ 未找到配置文件\n")

        if env_example.exists():
            print("发现 .env.example 文件")
            choice = input("是否复制 .env.example 为 .env？(y/n): ").strip().lower()
            if choice == 'y':
                import shutil
                shutil.copy(env_example, env_path)
                print(f"✅ 已创建：{env_path}\n")
        else:
            print("创建新的配置文件...\n")

    # 配置向导
    print("\n请输入配置信息：\n")

    # API Key
    print("GLM API Key:")
    print("  获取方式：")
    print("  1. 访问 https://open.bigmodel.cn/")
    print("  2. 注册/登录账号")
    print("  3. 在控制台获取 API Key\n")

    api_key = input("GLM_API_KEY: ").strip()

    # 模型选择
    print("\n选择模型：")
    print("  1. glm-4-flash   - 快速响应（默认）")
    print("  2. glm-4-plus    - 增强能力")
    print("  3. glm-4-air     - 性价比高")
    print("  4. glm-4-long    - 长上下文")
    print("  5. 其他模型\n")

    model_choice = input("选择 (1-5): ").strip()

    model_map = {
        "1": "glm-4-flash",
        "2": "glm-4-plus",
        "3": "glm-4-air",
        "4": "glm-4-long",
    }

    if model_choice in model_map:
        model = model_map[model_choice]
    elif model_choice == "5":
        model = input("输入模型名称: ").strip()
    else:
        model = "glm-4-flash"

    # 写入配置文件
    print(f"\n正在写入配置文件：{env_path}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("# GLM Provider 配置\n\n")
        f.write(f"GLM_API_KEY={api_key}\n")
        f.write(f"GLM_MODEL={model}\n")

    print("✅ 配置完成！\n")
    print("配置内容：")
    print(f"  GLM_API_KEY: {api_key[:20]}...{api_key[-10:]}")
    print(f"  GLM_MODEL: {model}\n")

    print("现在可以运行：")
    print("  python cli_glm.py\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
