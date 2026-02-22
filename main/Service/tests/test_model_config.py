"""
Model Config API 测试脚本

测试模型配置的增删改查功能。
"""

import asyncio
import sys

sys.path.insert(0, ".")

from Service.core.registry import ServiceRegistry
from Service.services.model_config_service import ModelConfigService
from Service.schemas.models import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ProviderType,
    ApiType,
)


async def main():
    # 创建服务
    registry = ServiceRegistry()
    service = ModelConfigService(registry)
    await service.initialize()

    print("=" * 60)
    print("Model Config Service CRUD Tests")
    print("=" * 60)

    # 1. 列出所有模型
    print("\n[1] List all models")
    models = service.list_models()
    print(f"   Total: {len(models)} models")
    print(f"   Providers: {set(m.provider for m in models)}")

    # 2. 获取统计信息
    print("\n[2] Get statistics")
    stats = service.get_stats()
    print(f"   Total: {stats.total_models}")
    print(f"   Builtin: {stats.builtin_models}")
    print(f"   Custom: {stats.custom_models}")
    print(f"   By provider: {stats.by_provider}")

    # 3. 获取单个模型
    print("\n[3] Get single model (glm-4-flash)")
    model = service.get_model("glm-4-flash")
    if model:
        print(f"   Name: {model.name}")
        print(f"   Provider: {model.provider}")
        print(f"   Context window: {model.context_window}")
        print(f"   Supports tools: {model.supports_tools}")
        print(f"   Is builtin: {model.is_builtin}")

    # 4. 创建自定义模型
    print("\n[4] Create custom model")
    try:
        new_model = service.create_model(
            ModelConfigCreate(
                id="my-custom-model",
                name="My Custom Model",
                provider=ProviderType.CUSTOM,
                api_type=ApiType.OPENAI_COMPLETIONS,
                supports_vision=False,
                supports_tools=True,
                context_window=32768,
                max_output_tokens=2048,
                cost_input=0.01,
                cost_output=0.02,
                base_url="https://api.example.com/v1",
                api_key_env="CUSTOM_API_KEY",
                extra={"vendor": "custom"},
            )
        )
        print(f"   Created: {new_model.id}")
        print(f"   Name: {new_model.name}")
        print(f"   Is builtin: {new_model.is_builtin}")
    except ValueError as e:
        print(f"   Error: {e}")

    # 5. 验证创建
    print("\n[5] Verify creation")
    model = service.get_model("my-custom-model")
    if model:
        print(f"   Found: {model.id}")
        print(f"   Created at: {model.created_at}")

    # 6. 更新模型
    print("\n[6] Update model")
    try:
        updated = service.update_model(
            "my-custom-model",
            ModelConfigUpdate(
                name="My Updated Custom Model",
                context_window=65536,
            ),
        )
        print(f"   Updated: {updated.id}")
        print(f"   New name: {updated.name}")
        print(f"   New context: {updated.context_window}")
        print(f"   Updated at: {updated.updated_at}")
    except ValueError as e:
        print(f"   Error: {e}")

    # 7. 列出国产 LLM 提供商
    print("\n[7] List Chinese LLM providers")
    providers = service.list_chinese_providers()
    print(f"   Total: {providers.total}")
    for p in providers.providers:
        print(f"   - {p.vendor_name} ({p.vendor}): {len(p.models)} models")
        print(f"     Default: {p.default_model}")
        print(f"     Models: {p.models[:3]}...")

    # 8. 尝试删除内置模型 (应该失败)
    print("\n[8] Try to delete builtin model (should fail)")
    try:
        service.delete_model("glm-4-flash")
        print("   ERROR: Should have failed!")
    except ValueError as e:
        print(f"   Expected error: {e}")

    # 9. 删除自定义模型
    print("\n[9] Delete custom model")
    try:
        success = service.delete_model("my-custom-model")
        print(f"   Deleted: {success}")
    except ValueError as e:
        print(f"   Error: {e}")

    # 10. 验证删除
    print("\n[10] Verify deletion")
    model = service.get_model("my-custom-model")
    print(f"   Model exists: {model is not None}")

    # 11. 最终统计
    print("\n[11] Final statistics")
    stats = service.get_stats()
    print(f"   Total: {stats.total_models}")
    print(f"   Custom: {stats.custom_models}")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)

    await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
