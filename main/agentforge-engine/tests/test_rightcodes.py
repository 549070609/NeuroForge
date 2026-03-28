"""
测试自定义 RightCodes 服务配置

验证配置是否正确加载并能成功调用 API
"""

import asyncio
import os
from pathlib import Path

# 加载 .env 文件
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / "main" / ".env"
load_dotenv(env_path)

from pyagentforge import LLMClient
from pyagentforge.kernel.model_registry import ModelRegistry


async def test_rightcodes_config():
    """测试 RightCodes 配置"""

    print("=" * 60)
    print("🔍 测试 RightCodes 配置")
    print("=" * 60)

    # 1. 检查环境变量
    print("\n1️⃣ 检查环境变量...")
    api_key = os.getenv("RIGHTCODES_API_KEY")
    base_url = os.getenv("RIGHTCODES_BASE_URL")

    print(f"   ✓ RIGHTCODES_API_KEY: {api_key[:20]}..." if api_key else "   ✗ 未设置")
    print(f"   ✓ RIGHTCODES_BASE_URL: {base_url}" if base_url else "   ✗ 未设置")

    if not api_key or not base_url:
        print("\n❌ 环境变量未正确设置！")
        return

    # 2. 检查模型注册
    print("\n2️⃣ 检查模型注册...")
    registry = ModelRegistry()

    model = registry.get_model("gpt-5.2-xhigh")
    if model:
        print(f"   ✓ 模型已注册: {model.name}")
        print(f"   ✓ Provider: {model.provider}")
        print(f"   ✓ API Type: {model.api_type}")
        print(f"   ✓ Base URL: {model.base_url}")
    else:
        print("   ✗ 模型未找到！")
        return

    # 3. 测试 API 调用
    print("\n3️⃣ 测试 API 调用...")
    client = LLMClient(registry=registry)

    try:
        response = await client.create_message(
            model_id="gpt-5.2-xhigh",
            messages=[{"role": "user", "content": "Hello! Please say 'Configuration test successful!' and nothing else."}],
            max_tokens=50,
        )

        print("\n✅ API 调用成功！")
        print(f"\n📝 模型响应:")
        print(f"   {response.text}")
        print(f"\n📊 使用统计:")
        print(f"   Input tokens: {response.usage.get('input_tokens', 'N/A')}")
        print(f"   Output tokens: {response.usage.get('output_tokens', 'N/A')}")
        print(f"   Stop reason: {response.stop_reason}")

    except Exception as e:
        print(f"\n❌ API 调用失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)


async def test_list_available_models():
    """列出所有可用模型"""

    print("\n📋 已注册的所有模型:")
    print("-" * 60)

    registry = ModelRegistry()
    models = registry.list_models()

    for model_id, model in models.items():
        print(f"  • {model_id}")
        print(f"    Name: {model.name}")
        print(f"    Provider: {model.provider.value}")
        print(f"    API Type: {model.api_type}")
        if model.base_url:
            print(f"    Base URL: {model.base_url}")
        print()


async def main():
    """主测试流程"""

    # 测试配置
    await test_rightcodes_config()

    # 列出所有模型
    await test_list_available_models()


if __name__ == "__main__":
    asyncio.run(main())