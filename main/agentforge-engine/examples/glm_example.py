"""
GLM Provider 使用示例

演示如何使用 PyAgentForge 的 GLM Provider 调用智谱 AI 的 GLM 模型
"""

import asyncio
import os

# 设置 API Key (实际使用时请从环境变量获取)
# os.environ["GLM_API_KEY"] = "your-api-key-here"


async def test_openai_endpoint():
    """测试 OpenAI 兼容端点"""
    from pyagentforge.providers import GLMProvider, GLMEndpoint

    provider = GLMProvider(
        api_key=os.environ.get("GLM_API_KEY"),
        model="glm-4-flash",
        endpoint=GLMEndpoint.OPENAI,
    )

    response = await provider.create_message(
        system="你是一个友好的助手。",
        messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
        tools=[],
    )

    print("=== OpenAI Endpoint ===")
    print(f"Response: {response.text}")
    print(f"Stop reason: {response.stop_reason}")
    print(f"Usage: {response.usage}")


async def test_anthropic_endpoint():
    """测试 Anthropic 兼容端点"""
    from pyagentforge.providers import GLMProvider, GLMEndpoint

    provider = GLMProvider(
        api_key=os.environ.get("GLM_API_KEY"),
        model="glm-4-flash",
        endpoint=GLMEndpoint.ANTHROPIC,
    )

    response = await provider.create_message(
        system="你是一个友好的助手。",
        messages=[{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
        tools=[],
    )

    print("\n=== Anthropic Endpoint ===")
    print(f"Response: {response.text}")
    print(f"Stop reason: {response.stop_reason}")
    print(f"Usage: {response.usage}")


async def test_streaming_openai():
    """测试 OpenAI 端点流式输出"""
    from pyagentforge.providers import GLMProvider, GLMEndpoint

    provider = GLMProvider(
        api_key=os.environ.get("GLM_API_KEY"),
        model="glm-4-flash",
        endpoint=GLMEndpoint.OPENAI,
    )

    print("\n=== Streaming (OpenAI Endpoint) ===")
    print("Response: ", end="", flush=True)

    async for chunk in provider.stream_message(
        system="你是一个友好的助手。",
        messages=[{"role": "user", "content": "用三句话介绍 Python 编程语言。"}],
        tools=[],
    ):
        if isinstance(chunk, dict) and chunk.get("type") == "text":
            print(chunk["text"], end="", flush=True)
        elif hasattr(chunk, "text"):
            # 最终的 ProviderResponse
            print(f"\n[Done] Usage: {chunk.usage}")


async def test_streaming_anthropic():
    """测试 Anthropic 端点流式输出"""
    from pyagentforge.providers import GLMProvider, GLMEndpoint

    provider = GLMProvider(
        api_key=os.environ.get("GLM_API_KEY"),
        model="glm-4-flash",
        endpoint=GLMEndpoint.ANTHROPIC,
    )

    print("\n=== Streaming (Anthropic Endpoint) ===")
    print("Response: ", end="", flush=True)

    async for chunk in provider.stream_message(
        system="你是一个友好的助手。",
        messages=[{"role": "user", "content": "用三句话介绍 Python 编程语言。"}],
        tools=[],
    ):
        if isinstance(chunk, dict) and chunk.get("type") == "text":
            print(chunk["text"], end="", flush=True)
        elif hasattr(chunk, "text"):
            # 最终的 ProviderResponse
            print(f"\n[Done] Usage: {chunk.usage}")


async def test_tool_calling():
    """测试工具调用"""
    from pyagentforge.providers import GLMProvider, GLMEndpoint

    provider = GLMProvider(
        api_key=os.environ.get("GLM_API_KEY"),
        model="glm-4-flash",
        endpoint=GLMEndpoint.OPENAI,
    )

    tools = [
        {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京",
                    }
                },
                "required": ["city"],
            },
        }
    ]

    response = await provider.create_message(
        system="你是一个助手，可以使用工具获取信息。",
        messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
        tools=tools,
    )

    print("\n=== Tool Calling ===")
    print(f"Response text: {response.text}")
    print(f"Has tool calls: {response.has_tool_calls}")
    if response.has_tool_calls:
        for tc in response.tool_calls:
            print(f"  Tool: {tc.name}, Args: {tc.input}")


async def test_factory_creation():
    """测试通过工厂创建 Provider"""
    from pyagentforge.providers import create_provider, get_supported_models

    # 获取支持的模型列表
    models = get_supported_models()
    glm_models = [m for m in models if m.startswith("glm")]
    print(f"\n=== Supported GLM Models ===")
    print(f"Models: {glm_models}")

    # 通过工厂创建 Provider
    provider = create_provider("glm-4-flash", api_key=os.environ.get("GLM_API_KEY"))
    print(f"\nCreated via factory: {type(provider).__name__}")
    print(f"Model: {provider.model}")
    print(f"Endpoint: {provider.endpoint}")


async def main():
    """主函数"""
    if not os.environ.get("GLM_API_KEY"):
        print("请设置 GLM_API_KEY 环境变量后运行此示例")
        print("示例: export GLM_API_KEY=your-api-key")
        return

    await test_openai_endpoint()
    await test_anthropic_endpoint()
    await test_streaming_openai()
    await test_streaming_anthropic()
    await test_tool_calling()
    await test_factory_creation()


if __name__ == "__main__":
    asyncio.run(main())
