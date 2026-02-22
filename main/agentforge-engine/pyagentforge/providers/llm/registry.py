"""
国产大模型 LLM 注册中心

提供可扩展的注册机制，支持智谱 (GLM)、阿里 (Qwen)、深度求索 (DeepSeek) 等国产模型
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Type

if TYPE_CHECKING:
    from pyagentforge.providers.base import BaseProvider


@dataclass
class ChineseLLMInfo:
    """国产 LLM 信息"""

    vendor: str  # 厂商标识: "zhipu", "alibaba", "deepseek"
    vendor_name: str  # 厂商名称: "智谱", "阿里", "深度求索"
    models: list[str]  # 支持的模型列表
    provider_class: Type[Any]  # Provider 类 (使用 Any 避免 TYPE_CHECKING 问题)
    default_model: str  # 默认模型
    api_key_env: str  # API Key 环境变量名
    base_url: str  # API 基础 URL
    description: str = ""  # 厂商描述
    extra: dict[str, Any] = field(default_factory=dict)  # 额外配置


class ChineseLLMRegistry:
    """国产 LLM 注册中心

    用于注册和管理国产大模型 Provider

    Example:
        @register_chinese_llm(
            vendor="zhipu",
            vendor_name="智谱",
            models=["glm-4-flash", "glm-4.7", "glm-5"],
            default_model="glm-4-flash",
            api_key_env="GLM_API_KEY",
            base_url="https://open.bigmodel.cn/api/paas/v4",
        )
        class GLMProvider(BaseProvider):
            ...
    """

    _registry: dict[str, ChineseLLMInfo] = {}

    @classmethod
    def register(
        cls,
        vendor: str,
        vendor_name: str,
        models: list[str],
        default_model: str,
        api_key_env: str,
        base_url: str,
        description: str = "",
        extra: dict[str, Any] | None = None,
    ) -> Callable[[Type[Any]], Type[Any]]:
        """
        装饰器：注册国产 LLM Provider

        Args:
            vendor: 厂商标识 (如 "zhipu", "alibaba", "deepseek")
            vendor_name: 厂商中文名称
            models: 支持的模型列表
            default_model: 默认模型
            api_key_env: API Key 环境变量名
            base_url: API 基础 URL
            description: 厂商描述
            extra: 额外配置

        Returns:
            装饰器函数
        """

        def decorator(provider_class: Type[Any]) -> Type[Any]:
            info = ChineseLLMInfo(
                vendor=vendor,
                vendor_name=vendor_name,
                models=models,
                provider_class=provider_class,
                default_model=default_model,
                api_key_env=api_key_env,
                base_url=base_url,
                description=description,
                extra=extra or {},
            )
            cls._registry[vendor] = info
            return provider_class

        return decorator

    @classmethod
    def get_provider(cls, vendor: str) -> ChineseLLMInfo | None:
        """
        获取厂商 Provider 信息

        Args:
            vendor: 厂商标识

        Returns:
            Provider 信息，如果不存在返回 None
        """
        return cls._registry.get(vendor)

    @classmethod
    def get_all_providers(cls) -> dict[str, ChineseLLMInfo]:
        """获取所有已注册的 Provider"""
        return cls._registry.copy()

    @classmethod
    def get_vendor_for_model(cls, model_id: str) -> str | None:
        """
        根据模型 ID 查找对应的厂商

        Args:
            model_id: 模型 ID

        Returns:
            厂商标识，如果找不到返回 None
        """
        for vendor, info in cls._registry.items():
            if model_id in info.models:
                return vendor
        return None

    @classmethod
    def is_registered(cls, vendor: str) -> bool:
        """检查厂商是否已注册"""
        return vendor in cls._registry

    @classmethod
    def create_provider(
        cls,
        vendor: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> Any | None:  # BaseProvider 实例或 None
        """
        创建 Provider 实例

        Args:
            vendor: 厂商标识
            model: 模型 ID，如果不指定则使用默认模型
            **kwargs: 传递给 Provider 的额外参数

        Returns:
            Provider 实例，如果厂商未注册返回 None
        """
        info = cls.get_provider(vendor)
        if not info:
            return None

        model_id = model or info.default_model
        return info.provider_class(model=model_id, **kwargs)


# 便捷别名
register_chinese_llm = ChineseLLMRegistry.register
