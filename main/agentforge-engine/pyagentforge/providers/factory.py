"""
模型适配器工厂

根据模型 ID 自动创建对应的 Provider 实例
"""

import os
from typing import Any

from pyagentforge.kernel.model_registry import (
    ModelConfig,
    ModelRegistry,
    ProviderType,
    get_registry,
)
from pyagentforge.providers.base import BaseProvider
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ModelAdapterFactory:
    """模型适配器工厂 - 根据模型 ID 创建 Provider"""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        """
        初始化工厂

        Args:
            registry: 模型注册表，如果为 None 则使用全局注册表
        """
        self.registry = registry or get_registry()
        self._provider_cache: dict[str, BaseProvider] = {}

    def _resolve_api_key(self, config: ModelConfig) -> str | None:
        """Resolve API key from env first, then centralized JSON config."""
        if config.api_key_env:
            key = os.environ.get(config.api_key_env)
            if key:
                return key

        try:
            from pyagentforge.config.llm_config import get_llm_config_manager

            manager = get_llm_config_manager()
            provider = config.provider.value if hasattr(config.provider, "value") else str(config.provider)
            key = manager.get_api_key(provider, config.id)
            if key and config.api_key_env and not os.environ.get(config.api_key_env):
                os.environ[config.api_key_env] = key
            return key
        except Exception:
            return None

    def create_provider(
        self,
        model_id: str,
        **kwargs: Any,
    ) -> BaseProvider:
        """
        根据模型 ID 创建 Provider 实例

        Args:
            model_id: 模型 ID
            **kwargs: 传递给 Provider 的额外参数

        Returns:
            Provider 实例

        Raises:
            ValueError: 如果模型未找到或 Provider 未注册
        """
        # 检查缓存
        cache_key = f"{model_id}:{hash(frozenset(kwargs.items()))}"
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]

        # 获取模型配置
        model_config = self.registry.get_model(model_id)
        if not model_config:
            raise ValueError(f"Model not found: {model_id}")

        # 创建 Provider
        provider = self._create_provider_for_model(model_config, **kwargs)

        # 缓存
        self._provider_cache[cache_key] = provider

        logger.info(
            "Created provider for model",
            extra_data={
                "model_id": model_id,
                "provider_type": model_config.provider.value,
            },
        )

        return provider

    def _create_provider_for_model(
        self,
        config: ModelConfig,
        **kwargs: Any,
    ) -> BaseProvider:
        """
        根据模型配置创建 Provider

        Args:
            config: 模型配置
            **kwargs: 额外参数

        Returns:
            Provider 实例
        """
        provider_type = config.provider

        # 合并配置参数
        provider_kwargs = {
            "model": config.id,
            "max_tokens": kwargs.get("max_tokens", config.max_output_tokens),
            "temperature": kwargs.get("temperature", 1.0),
            **config.extra,
            **kwargs,
        }

        # 根据提供商类型创建实例
        if provider_type == ProviderType.ANTHROPIC:
            return self._create_anthropic_provider(config, provider_kwargs)
        elif provider_type == ProviderType.OPENAI:
            return self._create_openai_provider(config, provider_kwargs)
        elif provider_type == ProviderType.GOOGLE:
            return self._create_google_provider(config, provider_kwargs)
        elif provider_type == ProviderType.AZURE:
            return self._create_azure_provider(config, provider_kwargs)
        elif provider_type == ProviderType.BEDROCK:
            return self._create_bedrock_provider(config, provider_kwargs)
        elif provider_type == ProviderType.CUSTOM:
            return self._create_custom_provider(config, provider_kwargs)
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")

    def _create_anthropic_provider(
        self,
        config: ModelConfig,
        kwargs: dict[str, Any],
    ) -> BaseProvider:
        """创建 Anthropic Provider"""
        from pyagentforge.providers.anthropic_provider import AnthropicProvider

        # 从环境变量获取 API Key
        api_key = self._resolve_api_key(config)

        return AnthropicProvider(
            api_key=api_key,
            **kwargs,
        )

    def _create_openai_provider(
        self,
        config: ModelConfig,
        kwargs: dict[str, Any],
    ) -> BaseProvider:
        """创建 OpenAI Provider"""
        from pyagentforge.providers.openai_provider import OpenAIProvider

        # 从环境变量获取 API Key
        api_key = self._resolve_api_key(config)

        provider_kwargs = {
            "api_key": api_key,
            **kwargs,
        }

        # 设置 base_url（如果有）
        if config.base_url:
            provider_kwargs["base_url"] = config.base_url

        return OpenAIProvider(**provider_kwargs)

    def _create_google_provider(
        self,
        config: ModelConfig,
        kwargs: dict[str, Any],
    ) -> BaseProvider:
        """创建 Google Provider"""
        # 尝试导入 Google Provider
        try:
            from pyagentforge.providers.google_provider import GoogleProvider

            api_key = self._resolve_api_key(config)

            return GoogleProvider(
                api_key=api_key,
                **kwargs,
            )
        except ImportError:
            raise ImportError(
                "Google Provider not implemented. "
                "Please implement pyagentforge.providers.google_provider.GoogleProvider"
            )

    def _create_azure_provider(
        self,
        config: ModelConfig,
        kwargs: dict[str, Any],
    ) -> BaseProvider:
        """创建 Azure Provider"""
        # 尝试导入 Azure Provider
        try:
            from pyagentforge.providers.azure_provider import AzureProvider

            api_key = self._resolve_api_key(config)

            return AzureProvider(
                api_key=api_key,
                endpoint=config.base_url,
                **kwargs,
            )
        except ImportError:
            raise ImportError(
                "Azure Provider not implemented. "
                "Please implement pyagentforge.providers.azure_provider.AzureProvider"
            )

    def _create_bedrock_provider(
        self,
        config: ModelConfig,
        kwargs: dict[str, Any],
    ) -> BaseProvider:
        """创建 Bedrock Provider"""
        # 尝试导入 Bedrock Provider
        try:
            from pyagentforge.providers.bedrock_provider import BedrockProvider

            return BedrockProvider(
                model_id=config.id,
                **kwargs,
            )
        except ImportError:
            raise ImportError(
                "Bedrock Provider not implemented. "
                "Please implement pyagentforge.providers.bedrock_provider.BedrockProvider"
            )

    def _create_custom_provider(
        self,
        config: ModelConfig,
        kwargs: dict[str, Any],
    ) -> BaseProvider:
        """创建自定义 Provider"""
        # 检查是否有 vendor 标记（用于国产 LLM）
        vendor = config.extra.get("vendor") if config.extra else None

        if vendor:
            # 尝试从 ChineseLLMRegistry 创建
            from pyagentforge.providers.llm.registry import ChineseLLMRegistry

            info = ChineseLLMRegistry.get_provider(vendor)
            if info:
                # 移除 model 键避免重复传递
                factory_kwargs = {k: v for k, v in kwargs.items() if k != "model"}
                return info.provider_class(model=config.id, **factory_kwargs)

        # 检查是否有自定义工厂
        provider_info = self.registry.get_provider(config.provider)
        if provider_info and provider_info.is_registered:
            # 注意: kwargs 已经包含 model 键，需要移除以避免重复传递
            factory_kwargs = {k: v for k, v in kwargs.items() if k != "model"}
            return provider_info.factory(model=config.id, **factory_kwargs)

        raise ValueError(
            f"Custom provider '{config.provider}' not registered. "
            f"Please register a factory using ModelRegistry.register_provider()"
        )

    def get_supported_models(self) -> list[str]:
        """获取所有支持的模型 ID"""
        return [m.id for m in self.registry.get_all_models()]

    def get_model_info(self, model_id: str) -> dict[str, Any] | None:
        """获取模型信息"""
        config = self.registry.get_model(model_id)
        if not config:
            return None

        return {
            "id": config.id,
            "name": config.name,
            "provider": config.provider.value,
            "api_type": config.api_type,
            "supports_vision": config.supports_vision,
            "supports_tools": config.supports_tools,
            "supports_streaming": config.supports_streaming,
            "context_window": config.context_window,
            "max_output_tokens": config.max_output_tokens,
            "cost_input": config.cost_input,
            "cost_output": config.cost_output,
        }


# 全局工厂实例
_factory: ModelAdapterFactory | None = None


def get_factory() -> ModelAdapterFactory:
    """获取全局工厂实例"""
    global _factory
    if _factory is None:
        _factory = ModelAdapterFactory()
    return _factory


def create_provider(model_id: str, **kwargs: Any) -> BaseProvider:
    """
    便捷函数：根据模型 ID 创建 Provider

    Args:
        model_id: 模型 ID
        **kwargs: 传递给 Provider 的额外参数

    Returns:
        Provider 实例
    """
    return get_factory().create_provider(model_id, **kwargs)


def get_supported_models() -> list[str]:
    """获取所有支持的模型 ID"""
    return get_factory().get_supported_models()
