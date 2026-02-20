"""
验证提示词适配系统

测试不同模型的提示词适配功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from pyagentforge.kernel.model_registry import get_model, get_registry
from pyagentforge.prompts.adapter import get_prompt_adapter
from pyagentforge.prompts.base import AdaptationContext


def print_section(title: str) -> None:
    """打印分隔线"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def test_anthropic_extended_thinking():
    """测试 Claude Sonnet 4 Extended Thinking 变体"""
    print_section("测试 Claude Sonnet 4 Extended Thinking")

    model_id = "claude-sonnet-4-20250514"
    model_config = get_model(model_id)

    if not model_config:
        print(f"❌ 模型 {model_id} 未找到")
        return False

    adapter = get_prompt_adapter()
    context = AdaptationContext(
        model_id=model_id,
        model_config=model_config,
        base_prompt="You are a helpful assistant.",
        available_tools=[],
    )

    prompt = adapter.adapt_prompt(context)

    print(f"模型 ID: {model_id}")
    print(f"Provider: {model_config.provider}")
    print(f"\n适配后的提示词长度: {len(prompt)} 字符")
    print(f"\n前 200 字符:")
    print(prompt[:200] + "...")

    # 检查是否包含 Extended Thinking 相关内容
    if "Extended Thinking" in prompt or "深度思考" in prompt:
        print("\n[OK] 成功检测到 Extended Thinking 内容")
        return True
    else:
        print("\n[WARN] 未检测到 Extended Thinking 内容")
        return False


def test_google_concise():
    """测试 Google Gemini 简洁输出变体"""
    print_section("测试 Google Gemini 简洁输出")

    model_id = "gemini-2.0-flash"
    model_config = get_model(model_id)

    if not model_config:
        print(f"❌ 模型 {model_id} 未找到")
        return False

    adapter = get_prompt_adapter()
    context = AdaptationContext(
        model_id=model_id,
        model_config=model_config,
        base_prompt="You are a helpful assistant.",
        available_tools=[],
    )

    prompt = adapter.adapt_prompt(context)

    print(f"模型 ID: {model_id}")
    print(f"Provider: {model_config.provider}")
    print(f"\n适配后的提示词长度: {len(prompt)} 字符")
    print(f"\n前 200 字符:")
    print(prompt[:200] + "...")

    # 检查是否包含简洁输出相关内容
    if "简洁" in prompt or "concise" in prompt.lower():
        print("\n[OK] 成功检测到简洁输出内容")
        return True
    else:
        print("\n[WARN] 未检测到简洁输出内容")
        return False


def test_openai_autonomous():
    """测试 OpenAI 自主工作流变体"""
    print_section("测试 OpenAI 自主工作流")

    model_id = "gpt-4o"
    model_config = get_model(model_id)

    if not model_config:
        print(f"❌ 模型 {model_id} 未找到")
        return False

    adapter = get_prompt_adapter()
    context = AdaptationContext(
        model_id=model_id,
        model_config=model_config,
        base_prompt="You are a helpful assistant.",
        available_tools=[],
    )

    prompt = adapter.adapt_prompt(context)

    print(f"模型 ID: {model_id}")
    print(f"Provider: {model_config.provider}")
    print(f"\n适配后的提示词长度: {len(prompt)} 字符")
    print(f"\n前 200 字符:")
    print(prompt[:200] + "...")

    # 检查是否包含自主工作流相关内容
    if "自主" in prompt or "autonomous" in prompt.lower():
        print("\n[OK] 成功检测到自主工作流内容")
        return True
    else:
        print("\n[WARN] 未检测到自主工作流内容")
        return False


def test_capability_modules():
    """测试能力模块"""
    print_section("测试能力模块")

    model_id = "claude-sonnet-4-20250514"
    model_config = get_model(model_id)

    if not model_config:
        print(f"❌ 模型 {model_id} 未找到")
        return False

    adapter = get_prompt_adapter()
    context = AdaptationContext(
        model_id=model_id,
        model_config=model_config,
        base_prompt="You are a helpful assistant.",
        available_tools=[],
    )

    prompt = adapter.adapt_prompt(context)

    print(f"模型 ID: {model_id}")
    print(f"支持视觉: {model_config.supports_vision}")

    # 检查能力模块
    checks = {
        "视觉能力": "图像处理" in prompt,
        "并行工具": "并行工具" in prompt or "并行执行" in prompt,
    }

    all_passed = True
    for name, passed in checks.items():
        status = "[OK]" if passed else "[WARN]"
        print(f"{status} {name}: {'检测到' if passed else '未检测到'}")
        if not passed:
            all_passed = False

    return all_passed


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  PyAgentForge 提示词适配系统验证")
    print("=" * 60)

    # 初始化注册表
    from pyagentforge.prompts.registry import get_prompt_registry

    registry = get_prompt_registry()
    print(f"\n已注册 {len(registry._variants)} 个提示词变体")
    print(f"已注册 {len(registry._capabilities)} 个能力模块")

    # 运行测试
    results = {
        "Claude Sonnet 4 Extended Thinking": test_anthropic_extended_thinking(),
        "Google Gemini 简洁输出": test_google_concise(),
        "OpenAI 自主工作流": test_openai_autonomous(),
        "能力模块": test_capability_modules(),
    }

    # 总结
    print_section("测试总结")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")

    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过！")
        return 0
    else:
        print("\n[WARNING] 部分测试未通过，请检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
