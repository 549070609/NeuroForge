"""
LLM 配置管理模块

支持从 JSON 文件加载 LLM 连接参数，配置路径通过环境变量 `LLM_CONFIG_PATH` 指定。
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# 使用标准 logging 避免循环导入
logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """单个 Provider 配置"""

    enabled: bool = Field(default=True, description="是否启用此 Provider")
    api_key: str | None = Field(default=None, description="API Key（可选，优先从环境变量读取）")
    api_key_env: str = Field(default="", description="API Key 环境变量名")
    base_url: str | None = Field(default=None, description="API 基础 URL")
    timeout: int = Field(default=120, description="请求超时时间（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")
    extra: dict[str, Any] = Field(default_factory=dict, description="额外配置")


class ModelConfig(BaseModel):
    """模型配置"""

    id: str = Field(..., description="模型 ID")
    name: str = Field(..., description="显示名称")
    provider: str = Field(..., description="提供商类型: anthropic, openai, google, custom")
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

    # 覆盖 Provider 配置
    api_key: str | None = Field(default=None, description="模型级 API Key（覆盖 Provider 配置）")
    api_key_env: str | None = Field(default=None, description="模型级 API Key 环境变量名")
    base_url: str | None = Field(default=None, description="模型级 API 基础 URL")

    # 额外配置
    extra: dict[str, Any] = Field(default_factory=dict, description="额外配置")


class LLMConfig(BaseModel):
    """LLM 完整配置"""

    # 默认模型
    default_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="默认使用的模型",
    )

    # 默认参数
    max_tokens: int = Field(default=4096, description="默认最大输出 Token")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="默认温度参数")

    # Provider 配置
    providers: dict[str, ProviderConfig] = Field(
        default_factory=dict,
        description="Provider 配置映射",
    )

    # 模型配置
    models: dict[str, ModelConfig] = Field(
        default_factory=dict,
        description="模型配置映射",
    )

    @field_validator("providers", "models", mode="before")
    @classmethod
    def resolve_env_vars(cls, v: dict[str, Any]) -> dict[str, Any]:
        """递归解析配置中的环境变量"""
        return _resolve_env_vars_recursive(v)


def _resolve_env_vars_recursive(obj: Any) -> Any:
    """递归解析对象中的环境变量"""
    import re

    env_pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'

    def replace_env(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        return match.group(0)  # 保留原始值

    if isinstance(obj, str):
        return re.sub(env_pattern, replace_env, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars_recursive(item) for item in obj]
    return obj


class LLMConfigManager:
    """LLM 配置管理器"""

    DEFAULT_CONFIG_PATH = "llm_config.json"
    ENV_CONFIG_PATH = "LLM_CONFIG_PATH"

    _instance: "LLMConfigManager | None" = None
    _config: LLMConfig | None = None
    _config_path: Path | None = None

    def __new__(cls) -> "LLMConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_config_path(self) -> Path:
        """获取配置文件路径"""
        # 优先使用环境变量
        env_path = os.environ.get(self.ENV_CONFIG_PATH)
        if env_path:
            return Path(env_path)

        # 其次查找默认路径
        cwd_path = Path.cwd() / self.DEFAULT_CONFIG_PATH
        if cwd_path.exists():
            return cwd_path

        # 最后使用包内默认配置
        return Path(__file__).parent / "default_llm_config.json"

    def load_config(self, config_path: str | Path | None = None) -> LLMConfig:
        """
        加载配置

        Args:
            config_path: 配置文件路径，如果为 None 则自动查找

        Returns:
            LLMConfig 实例
        """
        if config_path:
            path = Path(config_path)
        else:
            path = self.get_config_path()

        self._config_path = path

        if not path.exists():
            logger.warning(
                f"LLM config file not found: {path}, using defaults",
            )
            self._config = LLMConfig()
            return self._config

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._config = LLMConfig(**data)
            logger.info(
                f"Loaded LLM config from {path}",
                extra_data={
                    "providers": len(self._config.providers),
                    "models": len(self._config.models),
                },
            )
            return self._config

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {path}", extra_data={"error": str(e)})
            raise ValueError(f"Invalid JSON in config file: {path}") from e
        except Exception as e:
            logger.error(f"Failed to load config: {path}", extra_data={"error": str(e)})
            raise

    def get_config(self) -> LLMConfig:
        """获取当前配置（如果未加载则自动加载）"""
        if self._config is None:
            self.load_config()
        return self._config

    def reload_config(self) -> LLMConfig:
        """重新加载配置"""
        self._config = None
        return self.load_config(self._config_path)

    def get_provider_config(self, provider: str) -> ProviderConfig | None:
        """获取指定 Provider 的配置"""
        config = self.get_config()
        return config.providers.get(provider)

    def get_model_config(self, model_id: str) -> ModelConfig | None:
        """获取指定模型的配置"""
        config = self.get_config()
        return config.models.get(model_id)

    def get_api_key(self, provider: str, model_id: str | None = None) -> str | None:
        """
        获取 API Key

        优先级: 模型配置 > Provider 配置 > 环境变量

        Args:
            provider: Provider 名称
            model_id: 模型 ID（可选）

        Returns:
            API Key 或 None
        """
        # 1. 检查模型级配置
        if model_id:
            model_config = self.get_model_config(model_id)
            if model_config:
                if model_config.api_key:
                    return model_config.api_key
                if model_config.api_key_env:
                    key = os.environ.get(model_config.api_key_env)
                    if key:
                        return key

        # 2. 检查 Provider 配置
        provider_config = self.get_provider_config(provider)
        if provider_config:
            if provider_config.api_key:
                return provider_config.api_key
            if provider_config.api_key_env:
                key = os.environ.get(provider_config.api_key_env)
                if key:
                    return key

        # 3. 使用默认环境变量名
        default_env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "zhipu": "GLM_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        env_var = default_env_map.get(provider.lower())
        if env_var:
            return os.environ.get(env_var)

        return None

    def get_base_url(self, provider: str, model_id: str | None = None) -> str | None:
        """
        获取 API Base URL

        优先级: 模型配置 > Provider 配置 > None

        Args:
            provider: Provider 名称
            model_id: 模型 ID（可选）

        Returns:
            Base URL 或 None
        """
        # 1. 检查模型级配置
        if model_id:
            model_config = self.get_model_config(model_id)
            if model_config and model_config.base_url:
                return model_config.base_url

        # 2. 检查 Provider 配置
        provider_config = self.get_provider_config(provider)
        if provider_config and provider_config.base_url:
            return provider_config.base_url

        return None


def get_llm_config_manager() -> LLMConfigManager:
    """获取全局配置管理器实例"""
    return LLMConfigManager()


def get_llm_config() -> LLMConfig:
    """获取 LLM 配置"""
    return get_llm_config_manager().get_config()
