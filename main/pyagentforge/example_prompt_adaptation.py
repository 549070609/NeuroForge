"""
PyAgentForge 提示词适配系统使用示例

展示如何使用提示词适配系统为不同模型生成优化的系统提示词
"""

import asyncio
from pyagentforge.kernel.model_registry import get_model
from pyagentforge.prompts.adapter import get_prompt_adapter
from pyagentforge.prompts.base import AdaptationContext
from pyagentforge.prompts.registry import get_prompt_registry


def print_separator(title: str = ""):
    """打印分隔线"""
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


def show_registry_info():
    """显示注册表信息"""
    print_separator("提示词注册表信息")

    registry = get_prompt_registry()
    print(f"\n已注册的变体数量: {len(registry._variants)}")
    print("\n变体列表:")
    for i, variant in enumerate(registry._variants, 1):
        print(f"  {i}. {variant.name} (优先级: {variant.priority})")
        print(f"     模板: {variant.template_path}")

    print(f"\n已注册的能力模块数量: {len(registry._capabilities)}")
    print("\n能力模块列表:")
    for capability, module in registry._capabilities.items():
        print(f"  - {capability.value}: {module.description}")


def show_model_prompt(model_id: str, base_prompt: str = "You are a helpful assistant."):
    """显示特定模型的适配后提示词"""
    print_separator(f"模型: {model_id}")

    model_config = get_model(model_id)
    if not model_config:
        print(f"\n[错误] 模型 {model_id} 未找到")
        return

    adapter = get_prompt_adapter()
    context = AdaptationContext(
        model_id=model_id,
        model_config=model_config,
        base_prompt=base_prompt,
        available_tools=[],
    )

    adapted_prompt = adapter.adapt_prompt(context)

    print(f"\n模型 ID: {model_id}")
    print(f"Provider: {model_config.provider}")
    print(f"支持视觉: {model_config.supports_vision}")
    print(f"支持工具: {model_config.supports_tools}")
    print(f"\n基础提示词长度: {len(base_prompt)} 字符")
    print(f"适配后提示词长度: {len(adapted_prompt)} 字符")
    print(f"\n适配后的提示词预览 (前 300 字符):")
    print("-" * 70)
    print(adapted_prompt[:300] + "...")
    print("-" * 70)


def show_full_adapted_prompt(model_id: str):
    """显示完整适配后的提示词"""
    print_separator(f"完整提示词示例: {model_id}")

    model_config = get_model(model_id)
    if not model_config:
        print(f"\n[错误] 模型 {model_id} 未找到")
        return

    adapter = get_prompt_adapter()
    context = AdaptationContext(
        model_id=model_id,
        model_config=model_config,
        base_prompt="You are a helpful assistant.",
        available_tools=[
            {
                "name": "bash",
                "description": "Execute bash commands",
            },
            {
                "name": "read",
                "description": "Read file contents",
            },
        ],
    )

    adapted_prompt = adapter.adapt_prompt(context)

    print(f"\n{adapted_prompt}")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  PyAgentForge 提示词适配系统 - 使用示例")
    print("=" * 70)

    # 1. 显示注册表信息
    show_registry_info()

    # 2. 显示不同模型的适配后提示词预览
    models = [
        "claude-sonnet-4-20250514",  # Extended Thinking
        "claude-3-5-sonnet-20241022",  # Standard Anthropic
        "gemini-2.0-flash",  # Google
        "gpt-4o",  # OpenAI
    ]

    for model_id in models:
        show_model_prompt(model_id)

    # 3. 显示 Claude Sonnet 4 的完整提示词
    show_full_adapted_prompt("claude-sonnet-4-20250514")

    print_separator("示例结束")
    print("\n提示: 提示词适配系统会根据以下因素自动适配:")
    print("  1. 模型提供商 (Anthropic/OpenAI/Google)")
    print("  2. 模型特定能力 (Vision/Extended Thinking)")
    print("  3. 可用工具")
    print("\n")


if __name__ == "__main__":
    main()
