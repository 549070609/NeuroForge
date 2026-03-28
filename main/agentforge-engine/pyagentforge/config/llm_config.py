"""
LLM 配置管理模块

仅保留模型级连接参数：兼容格式、基础 URL、模型名、认证与请求控制。
配置路径通过环境变量 `LLM_CONFIG_PATH` 指定。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class ModelConfig(BaseModel):
    """模型配置。"""

    id: str = Field(..., description="模型 ID")
    name: str = Field(..., description="显示名称")
    provider: str = Field(..., description="供应商标识，仅用于分组展示")
    api_type: Literal[
        "anthropic-messages",
        "openai-completions",
        "openai-responses",
        "google-generative-ai",
        "bedrock-converse-stream",
        "custom",
    ] = Field(..., description="兼容协议类型")
    model_name: str | None = Field(default=None, description="实际请求时使用的模型名")

    supports_vision: bool = Field(default=False, description="是否支持图像")
    supports_tools: bool = Field(default=True, description="是否支持工具调用")
    supports_streaming: bool = Field(default=True, description="是否支持流式")

    context_window: int = Field(default=200000, description="上下文窗口大小")
    max_output_tokens: int = Field(default=4096, description="最大输出 tokens")

    cost_input: float = Field(default=0.0, description="输入成本/百万 tokens")
    cost_output: float = Field(default=0.0, description="输出成本/百万 tokens")
    cost_cache_read: float = Field(default=0.0, description="缓存读取成本/百万 tokens")
    cost_cache_write: float = Field(default=0.0, description="缓存写入成本/百万 tokens")

    api_key: str | None = Field(default=None, description="直接传入的 API Key")
    api_key_env: str | None = Field(default=None, description="API Key 环境变量名")
    base_url: str | None = Field(default=None, description="API 基础 URL")
    timeout: int = Field(default=120, description="请求超时（秒）")
    headers: dict[str, str] = Field(default_factory=dict, description="附加请求头")
    extra: dict[str, Any] = Field(default_factory=dict, description="额外配置")


class LLMConfig(BaseModel):
    """LLM 完整配置。"""

    default_model: str = Field(default="default", description="默认模型 ID")
    max_tokens: int = Field(default=4096, description="默认最大输出 Token")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="默认温度参数")
    models: dict[str, ModelConfig] = Field(default_factory=dict, description="模型配置映射")

    @field_validator("models", mode="before")
    @classmethod
    def resolve_env_vars(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _resolve_env_vars_recursive(value)


def _resolve_env_vars_recursive(obj: Any) -> Any:
    import re

    env_pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'

    def replace_env(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_value = os.environ.get(var_name)
        if env_value is not None:
            return env_value
        if default is not None:
            return default
        return match.group(0)

    if isinstance(obj, str):
        return re.sub(env_pattern, replace_env, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_vars_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_vars_recursive(v) for v in obj]
    return obj


class LLMConfigManager:
    """LLM 配置管理器。"""

    DEFAULT_CONFIG_PATH = "llm_config.json"
    DEFAULT_FALLBACK_PATH = "default_llm_config.json"
    ENV_CONFIG_PATH = "LLM_CONFIG_PATH"

    def __init__(self) -> None:
        self._config: LLMConfig | None = None
        self._config_path: Path | None = None

    def _resolve_config_path(self, custom_path: str | Path | None = None) -> Path:
        if custom_path:
            return Path(custom_path)

        env_path = os.environ.get(self.ENV_CONFIG_PATH)
        if env_path:
            return Path(env_path)

        project_root = Path.cwd()
        primary = project_root / self.DEFAULT_CONFIG_PATH
        if primary.exists():
            return primary
        return project_root / self.DEFAULT_FALLBACK_PATH

    def load_config(self, path: str | Path | None = None) -> LLMConfig:
        self._config_path = self._resolve_config_path(path)
        path = self._config_path

        if not path.exists():
            logger.warning(f"LLM config file not found: {path}, using defaults")
            self._config = LLMConfig()
            return self._config

        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)

            self._config = LLMConfig(**data)
            logger.info(
                f"Loaded LLM config from {path}",
                extra={"models": len(self._config.models)},
            )
            return self._config
        except json.JSONDecodeError as exc:
            logger.error(f"Invalid JSON in config file: {path}", extra={"error": str(exc)})
            raise ValueError(f"Invalid JSON in config file: {path}") from exc
        except Exception as exc:
            logger.error(f"Failed to load config: {path}", extra={"error": str(exc)})
            raise

    def get_config(self) -> LLMConfig:
        if self._config is None:
            self.load_config()
        return self._config

    def reload_config(self) -> LLMConfig:
        self._config = None
        return self.load_config(self._config_path)

    def get_provider_config(self, provider: str) -> None:
        return None

    def get_model_config(self, model_id: str) -> ModelConfig | None:
        return self.get_config().models.get(model_id)

    def get_api_key(self, provider: str, model_id: str | None = None) -> str | None:
        if model_id:
            model_config = self.get_model_config(model_id)
            if model_config:
                if model_config.api_key:
                    return model_config.api_key
                if model_config.api_key_env:
                    return os.environ.get(model_config.api_key_env)
        return None

    def get_base_url(self, provider: str, model_id: str | None = None) -> str | None:
        if model_id:
            model_config = self.get_model_config(model_id)
            if model_config:
                return model_config.base_url
        return None


def get_llm_config_manager() -> LLMConfigManager:
    return LLMConfigManager()


def get_llm_config() -> LLMConfig:
    return get_llm_config_manager().get_config()
