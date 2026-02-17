"""
大模型适配新功能使用示例

展示上下文压缩、思考级别控制、动态模型注册的使用方法
"""

import asyncio

from pyagentforge.config.settings import get_settings
from pyagentforge.core.compaction import Compactor, CompactionSettings
from pyagentforge.core.engine import AgentEngine
from pyagentforge.core.model_registry import (
    ModelConfig,
    ModelRegistry,
    ProviderType,
    get_registry,
    register_model,
)
from pyagentforge.core.thinking import (
    ThinkingLevel,
    ThinkingConfig,
    create_thinking_config,
    supports_thinking,
)
from pyagentforge.providers.anthropic_provider import AnthropicProvider
from pyagentforge.tools.registry import ToolRegistry


async def example_thinking_level():
    """示例：思考级别控制"""
    print("\n=== 思考级别控制示例 ===\n")

    # 1. 检查模型是否支持思考
    model_id = "claude-sonnet-4-20250514"
    if supports_thinking(model_id):
        print(f"模型 {model_id} 支持扩展思考")

    # 2. 创建思考配置
    config = create_thinking_config(
        level=ThinkingLevel.HIGH,
        model_id=model_id,
    )
    print(f"思考级别: {config.level.value}")
    print(f"思考预算: {config.budget_tokens} tokens")

    # 3. 转换为 API 参数
    anthropic_params = config.to_anthropic_params()
    print(f"Anthropic 参数: {anthropic_params}")

    # 4. 在 Agent 中使用
    settings = get_settings()
    if settings.anthropic_api_key:
        provider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=model_id,
        )
        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
            thinking_level=ThinkingLevel.MEDIUM,  # 设置思考级别
        )
        print(f"Agent 思考级别: {engine.thinking_level.value}")

    # 5. 动态调整思考级别
    if "engine" in dir():
        engine.set_thinking_level(ThinkingLevel.HIGH)
        print(f"调整后思考级别: {engine.thinking_level.value}")


async def example_compaction():
    """示例：上下文压缩"""
    print("\n=== 上下文压缩示例 ===\n")

    settings = get_settings()
    if not settings.anthropic_api_key:
        print("需要设置 ANTHROPIC_API_KEY")
        return

    # 1. 创建 Provider
    provider = AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model="claude-sonnet-4-20250514",
    )

    # 2. 创建压缩器
    compactor = Compactor(
        provider=provider,
        settings=CompactionSettings(
            enabled=True,
            reserve_tokens=8000,
            keep_recent_tokens=4000,
            trigger_threshold=0.8,
        ),
        max_context_tokens=200000,
    )

    # 3. 检查是否需要压缩
    from pyagentforge.core.message import Message

    # 模拟一些消息
    messages = [
        Message.user_message("你好，请帮我分析一下这个项目"),
        Message.assistant_text("好的，我来帮你分析..."),
    ]

    if compactor.should_compact(messages):
        print("需要压缩上下文")
        result = await compactor.compact(messages)
        print(f"压缩结果: 移除 {result.removed_messages} 条消息")
        print(f"节省 {result.tokens_saved} tokens")
    else:
        print("当前不需要压缩")

    # 4. 在 Agent 中自动使用
    engine = AgentEngine(
        provider=provider,
        tool_registry=ToolRegistry(),
    )
    # Agent 在执行过程中会自动检查并压缩


async def example_model_registry():
    """示例：动态模型注册"""
    print("\n=== 动态模型注册示例 ===\n")

    # 1. 获取全局注册表
    registry = get_registry()

    # 2. 查询内置模型
    model = registry.get_model("claude-sonnet-4-20250514")
    if model:
        print(f"模型名称: {model.name}")
        print(f"上下文窗口: {model.context_window}")
        print(f"支持工具: {model.supports_tools}")

    # 3. 注册自定义模型
    custom_model = ModelConfig(
        id="my-custom-model",
        name="My Custom Model",
        provider=ProviderType.OPENAI,
        api_type="openai-completions",
        context_window=32000,
        max_output_tokens=4096,
        base_url="https://api.example.com/v1",
        api_key_env="CUSTOM_API_KEY",
        cost_input=0.5,
        cost_output=1.5,
    )
    register_model(custom_model, aliases=["custom", "mcm"])
    print(f"\n已注册自定义模型: {custom_model.id}")

    # 4. 通过别名查找
    model = registry.get_model("custom")
    if model:
        print(f"通过别名找到: {model.name}")

    # 5. 计算成本
    cost = model.calculate_cost(
        input_tokens=10000,
        output_tokens=2000,
    )
    print(f"调用成本: ${cost:.4f}")

    # 6. 获取所有模型
    all_models = registry.get_all_models()
    print(f"\n已注册 {len(all_models)} 个模型")

    # 7. 按 Provider 过滤
    anthropic_models = registry.get_models_by_provider(ProviderType.ANTHROPIC)
    print(f"Anthropic 模型: {len(anthropic_models)} 个")


async def example_full_integration():
    """示例：完整集成使用"""
    print("\n=== 完整集成示例 ===\n")

    settings = get_settings()
    if not settings.anthropic_api_key:
        print("需要设置 ANTHROPIC_API_KEY")
        return

    # 1. 从注册表获取模型配置
    registry = get_registry()
    model_config = registry.get_model("claude-sonnet-4-20250514")
    print(f"使用模型: {model_config.name}")

    # 2. 创建 Provider
    provider = AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model=model_config.id,
        max_tokens=model_config.max_output_tokens,
    )

    # 3. 创建 Agent，启用思考
    engine = AgentEngine(
        provider=provider,
        tool_registry=ToolRegistry(),
        thinking_level=ThinkingLevel.MEDIUM,
    )

    print(f"Agent 配置:")
    print(f"  - 模型: {model_config.id}")
    print(f"  - 思考级别: {engine.thinking_level.value}")
    print(f"  - 压缩启用: {engine.compactor.settings.enabled}")

    # 4. 运行 Agent
    # response = await engine.run("请解释什么是递归？")
    # print(f"响应: {response}")

    # 5. 查看上下文摘要
    summary = engine.get_context_summary()
    print(f"\n上下文摘要:")
    for key, value in summary.items():
        print(f"  - {key}: {value}")


async def main():
    """运行所有示例"""
    await example_thinking_level()
    await example_compaction()
    await example_model_registry()
    await example_full_integration()


if __name__ == "__main__":
    asyncio.run(main())
