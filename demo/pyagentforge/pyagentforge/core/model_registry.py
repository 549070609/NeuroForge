"""
动态模型注册模块

支持运行时动态注册和管理 LLM 模型配置
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ProviderType(str, Enum):
    """Provider 类型"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE = "azure"
    BEDROCK = "bedrock"
    CUSTOM = "custom"


class ModelConfig(BaseModel):
    """模型配置"""

    id: str = Field(..., description="模型 ID")
    name: str = Field(..., description="显示名称")
    provider: ProviderType = Field(..., description="提供商类型")
    api_type: Literal[
        "anthropic-messages",
        "openai-completions",
        "openai-responses",
        "google-generative-ai",
        "bedrock-converse-stream",
        "custom",
    ] = Field(..., description="API 类型")

    # 模型能力
    supports_vision: bool = Field(default=False, description="是否支持图像")
    supports_tools: bool = Field(default=True, description="是否支持工具调用")
    supports_streaming: bool = Field(default=True, description="是否支持流式")

    # 上下文限制
    context_window: int = Field(default=200000, description="上下文窗口大小")
    max_output_tokens: int = Field(default=4096, description="最大输出 tokens")

    # 成本配置（每百万 tokens）
    cost_input: float = Field(default=0.0, description="输入成本/百万 tokens")
    cost_output: float = Field(default=0.0, description="输出成本/百万 tokens")
    cost_cache_read: float = Field(default=0.0, description="缓存读取成本/百万 tokens")
    cost_cache_write: float = Field(default=0.0, description="缓存写入成本/百万 tokens")

    # API 配置
    base_url: str | None = Field(default=None, description="API 基础 URL")
    api_key_env: str = Field(default="", description="API Key 环境变量名")

    # 额外配置
    extra: dict[str, Any] = Field(default_factory=dict, description="额外配置")

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> float:
        """
        计算调用成本

        Args:
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
            cache_read: 缓存读取 tokens
            cache_write: 缓存写入 tokens

        Returns:
            成本（美元）
        """
        cost = 0.0
        cost += (input_tokens / 1_000_000) * self.cost_input
        cost += (output_tokens / 1_000_000) * self.cost_output
        cost += (cache_read / 1_000_000) * self.cost_cache_read
        cost += (cache_write / 1_000_000) * self.cost_cache_write
        return cost


@dataclass
class ProviderInfo:
    """Provider 信息"""

    type: ProviderType
    name: str
    factory: Callable[..., Any]  # 创建 Provider 实例的工厂函数
    models: list[str] = field(default_factory=list)
    is_registered: bool = False


# 内置模型配置
BUILTIN_MODELS: dict[str, ModelConfig] = {
    # Anthropic Claude 模型
    "claude-sonnet-4-20250514": ModelConfig(
        id="claude-sonnet-4-20250514",
        name="Claude Sonnet 4",
        provider=ProviderType.ANTHROPIC,
        api_type="anthropic-messages",
        supports_vision=True,
        supports_tools=True,
        context_window=200000,
        max_output_tokens=16384,
        cost_input=3.0,
        cost_output=15.0,
        cost_cache_read=0.30,
        cost_cache_write=3.75,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "claude-3-5-sonnet-20241022": ModelConfig(
        id="claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet",
        provider=ProviderType.ANTHROPIC,
        api_type="anthropic-messages",
        supports_vision=True,
        supports_tools=True,
        context_window=200000,
        max_output_tokens=8192,
        cost_input=3.0,
        cost_output=15.0,
        cost_cache_read=0.30,
        cost_cache_write=3.75,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "claude-3-5-haiku-20241022": ModelConfig(
        id="claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        provider=ProviderType.ANTHROPIC,
        api_type="anthropic-messages",
        supports_vision=True,
        supports_tools=True,
        context_window=200000,
        max_output_tokens=8192,
        cost_input=0.80,
        cost_output=4.0,
        cost_cache_read=0.08,
        cost_cache_write=1.0,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    "claude-opus-4-20250514": ModelConfig(
        id="claude-opus-4-20250514",
        name="Claude Opus 4",
        provider=ProviderType.ANTHROPIC,
        api_type="anthropic-messages",
        supports_vision=True,
        supports_tools=True,
        context_window=200000,
        max_output_tokens=16384,
        cost_input=15.0,
        cost_output=75.0,
        cost_cache_read=1.50,
        cost_cache_write=18.75,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    # OpenAI 模型
    "gpt-4o": ModelConfig(
        id="gpt-4o",
        name="GPT-4o",
        provider=ProviderType.OPENAI,
        api_type="openai-completions",
        supports_vision=True,
        supports_tools=True,
        context_window=128000,
        max_output_tokens=16384,
        cost_input=2.50,
        cost_output=10.0,
        api_key_env="OPENAI_API_KEY",
    ),
    "gpt-4o-mini": ModelConfig(
        id="gpt-4o-mini",
        name="GPT-4o Mini",
        provider=ProviderType.OPENAI,
        api_type="openai-completions",
        supports_vision=True,
        supports_tools=True,
        context_window=128000,
        max_output_tokens=16384,
        cost_input=0.15,
        cost_output=0.60,
        api_key_env="OPENAI_API_KEY",
    ),
    "o1-preview": ModelConfig(
        id="o1-preview",
        name="o1 Preview",
        provider=ProviderType.OPENAI,
        api_type="openai-completions",
        supports_vision=False,
        supports_tools=False,
        context_window=128000,
        max_output_tokens=32768,
        cost_input=15.0,
        cost_output=60.0,
        api_key_env="OPENAI_API_KEY",
    ),
    "o3-mini": ModelConfig(
        id="o3-mini",
        name="o3 Mini",
        provider=ProviderType.OPENAI,
        api_type="openai-completions",
        supports_vision=False,
        supports_tools=True,
        context_window=200000,
        max_output_tokens=100000,
        cost_input=1.10,
        cost_output=4.40,
        api_key_env="OPENAI_API_KEY",
    ),
    # Google 模型
    "gemini-2.0-flash": ModelConfig(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider=ProviderType.GOOGLE,
        api_type="google-generative-ai",
        supports_vision=True,
        supports_tools=True,
        context_window=1048576,
        max_output_tokens=8192,
        cost_input=0.10,
        cost_output=0.40,
        api_key_env="GOOGLE_API_KEY",
    ),
}


class ModelRegistry:
    """模型注册表"""

    def __init__(self) -> None:
        """初始化模型注册表"""
        self._models: dict[str, ModelConfig] = {}
        self._providers: dict[ProviderType, ProviderInfo] = {}
        self._aliases: dict[str, str] = {}

        # 加载内置模型
        self._load_builtin_models()

    def _load_builtin_models(self) -> None:
        """加载内置模型"""
        for model_id, config in BUILTIN_MODELS.items():
            self._models[model_id] = config
        logger.info(
            "Loaded builtin models",
            extra_data={"count": len(BUILTIN_MODELS)},
        )

    def register_model(
        self,
        config: ModelConfig,
        aliases: list[str] | None = None,
    ) -> None:
        """
        注册模型

        Args:
            config: 模型配置
            aliases: 模型别名列表
        """
        self._models[config.id] = config

        if aliases:
            for alias in aliases:
                self._aliases[alias] = config.id

        logger.info(
            "Registered model",
            extra_data={"model_id": config.id, "aliases": aliases},
        )

    def unregister_model(self, model_id: str) -> bool:
        """
        注销模型

        Args:
            model_id: 模型 ID

        Returns:
            是否成功注销
        """
        if model_id in self._models:
            del self._models[model_id]
            # 清理别名
            self._aliases = {
                k: v for k, v in self._aliases.items() if v != model_id
            }
            logger.info("Unregistered model", extra_data={"model_id": model_id})
            return True
        return False

    def register_provider(
        self,
        provider_type: ProviderType,
        name: str,
        factory: Callable[..., Any],
        models: list[str] | None = None,
    ) -> None:
        """
        注册 Provider

        Args:
            provider_type: Provider 类型
            name: Provider 名称
            factory: 创建 Provider 实例的工厂函数
            models: 该 Provider 支持的模型列表
        """
        self._providers[provider_type] = ProviderInfo(
            type=provider_type,
            name=name,
            factory=factory,
            models=models or [],
            is_registered=True,
        )
        logger.info(
            "Registered provider",
            extra_data={"provider": name, "models": models},
        )

    def get_model(self, model_id: str) -> ModelConfig | None:
        """
        获取模型配置

        Args:
            model_id: 模型 ID 或别名

        Returns:
            模型配置，如果不存在返回 None
        """
        # 先检查别名
        if model_id in self._aliases:
            model_id = self._aliases[model_id]

        # 直接查找
        if model_id in self._models:
            return self._models[model_id]

        # 模糊匹配（部分 ID 匹配）
        model_id_lower = model_id.lower()
        for mid, config in self._models.items():
            if model_id_lower in mid.lower() or mid.lower() in model_id_lower:
                return config

        return None

    def get_all_models(self) -> list[ModelConfig]:
        """获取所有已注册的模型"""
        return list(self._models.values())

    def get_models_by_provider(self, provider: ProviderType) -> list[ModelConfig]:
        """
        获取指定 Provider 的所有模型

        Args:
            provider: Provider 类型

        Returns:
            模型配置列表
        """
        return [
            config
            for config in self._models.values()
            if config.provider == provider
        ]

    def get_provider(self, provider_type: ProviderType) -> ProviderInfo | None:
        """获取 Provider 信息"""
        return self._providers.get(provider_type)

    def resolve_model_pattern(self, pattern: str) -> tuple[ModelConfig | None, str | None]:
        """
        解析模型模式

        支持格式：
        - "model_id" -> (ModelConfig, None)
        - "model_id:thinking_level" -> (ModelConfig, "thinking_level")

        Args:
            pattern: 模型模式字符串

        Returns:
            (模型配置, 思考级别) 元组
        """
        parts = pattern.split(":", 1)
        model_id = parts[0]
        thinking_level = parts[1] if len(parts) > 1 else None

        config = self.get_model(model_id)
        return (config, thinking_level)

    def create_provider_instance(
        self,
        model_id: str,
        **kwargs: Any,
    ) -> Any:
        """
        创建 Provider 实例

        Args:
            model_id: 模型 ID
            **kwargs: 传递给工厂函数的参数

        Returns:
            Provider 实例
        """
        config = self.get_model(model_id)
        if not config:
            raise ValueError(f"Model not found: {model_id}")

        provider_info = self._providers.get(config.provider)
        if not provider_info or not provider_info.is_registered:
            raise ValueError(f"Provider not registered: {config.provider}")

        return provider_info.factory(model=config.id, **kwargs)

    def refresh(self) -> None:
        """刷新注册表（重新加载内置模型）"""
        self._models.clear()
        self._aliases.clear()
        self._load_builtin_models()


# 全局注册表实例
_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    """获取全局注册表实例"""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def register_model(config: ModelConfig, aliases: list[str] | None = None) -> None:
    """注册模型到全局注册表"""
    get_registry().register_model(config, aliases)


def get_model(model_id: str) -> ModelConfig | None:
    """从全局注册表获取模型配置"""
    return get_registry().get_model(model_id)


def register_provider(
    provider_type: ProviderType,
    name: str,
    factory: Callable[..., Any],
    models: list[str] | None = None,
) -> None:
    """注册 Provider 到全局注册表"""
    get_registry().register_provider(provider_type, name, factory, models)
