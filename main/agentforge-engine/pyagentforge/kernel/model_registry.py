"""
动态模型注册模块。

SDK 仅保留协议格式、模型参数与连接信息，不再内置厂商实现或内置模型列表。
"""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

ApiType = Literal[
    "anthropic-messages",
    "openai-completions",
    "openai-responses",
    "google-generative-ai",
    "bedrock-converse-stream",
    "custom",
]


class ModelConfig(BaseModel):
    """模型配置。"""

    id: str = Field(..., description="模型 ID")
    name: str = Field(..., description="显示名称")
    provider: str = Field(..., description="提供商标签，仅作分组展示")
    api_type: ApiType = Field(..., description="协议格式类型")
    model_name: str | None = Field(default=None, description="实际传给远端的模型名")

    supports_vision: bool = Field(default=False, description="是否支持图像")
    supports_tools: bool = Field(default=True, description="是否支持工具调用")
    supports_streaming: bool = Field(default=True, description="是否支持流式")

    context_window: int = Field(default=200000, description="上下文窗口大小")
    max_output_tokens: int = Field(default=4096, description="最大输出 tokens")

    cost_input: float = Field(default=0.0, description="输入成本/百万 tokens")
    cost_output: float = Field(default=0.0, description="输出成本/百万 tokens")
    cost_cache_read: float = Field(default=0.0, description="缓存读取成本/百万 tokens")
    cost_cache_write: float = Field(default=0.0, description="缓存写入成本/百万 tokens")

    base_url: str | None = Field(default=None, description="API 基础 URL")
    api_key: str | None = Field(default=None, description="直接传入的 API Key")
    api_key_env: str = Field(default="", description="API Key 环境变量名")
    headers: dict[str, str] = Field(default_factory=dict, description="附加请求头")
    timeout: int = Field(default=120, description="请求超时（秒）")

    extra: dict[str, Any] = Field(default_factory=dict, description="额外配置")

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: Any) -> str:
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @property
    def resolved_model_name(self) -> str:
        return self.model_name or self.id

    def resolve_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.environ.get(self.api_key_env, "")
        return ""

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> float:
        cost = 0.0
        cost += (input_tokens / 1_000_000) * self.cost_input
        cost += (output_tokens / 1_000_000) * self.cost_output
        cost += (cache_read / 1_000_000) * self.cost_cache_read
        cost += (cache_write / 1_000_000) * self.cost_cache_write
        return cost


class ModelRegistry:
    """模型注册表。"""

    def __init__(self, load_from_config: bool = True) -> None:
        self._config_models: dict[str, ModelConfig] = {}
        self._runtime_models: dict[str, ModelConfig] = {}
        self._aliases: dict[str, str] = {}
        if load_from_config:
            self._load_from_json_config()

    def _load_from_json_config(self) -> None:
        try:
            from pyagentforge.config.llm_config import get_llm_config_manager

            manager = get_llm_config_manager()
            config = manager.get_config()

            for model_id, model_cfg in config.models.items():
                api_key = model_cfg.api_key
                if not api_key and model_cfg.api_key_env:
                    api_key = os.environ.get(model_cfg.api_key_env)

                headers = {}
                if isinstance(model_cfg.headers, dict):
                    headers.update({str(k): str(v) for k, v in model_cfg.headers.items()})
                if isinstance(model_cfg.extra, dict):
                    extra_headers = model_cfg.extra.get("headers")
                    if isinstance(extra_headers, dict):
                        headers.update({str(k): str(v) for k, v in extra_headers.items()})

                self._config_models[model_id] = ModelConfig(
                    id=model_cfg.id,
                    name=model_cfg.name,
                    provider=model_cfg.provider,
                    api_type=model_cfg.api_type,
                    model_name=model_cfg.model_name or model_cfg.id,
                    supports_vision=model_cfg.supports_vision,
                    supports_tools=model_cfg.supports_tools,
                    supports_streaming=model_cfg.supports_streaming,
                    context_window=model_cfg.context_window,
                    max_output_tokens=model_cfg.max_output_tokens,
                    cost_input=model_cfg.cost_input,
                    cost_output=model_cfg.cost_output,
                    cost_cache_read=model_cfg.cost_cache_read,
                    cost_cache_write=model_cfg.cost_cache_write,
                    base_url=model_cfg.base_url,
                    api_key=api_key,
                    api_key_env=model_cfg.api_key_env or "",
                    headers=headers,
                    timeout=model_cfg.timeout,
                    extra=model_cfg.extra,
                )

            logger.info("Loaded models from JSON config", extra_data={"count": len(config.models)})
        except Exception as exc:
            logger.warning(f"Failed to load from JSON config: {exc}")

    def register_model(self, config: ModelConfig, aliases: list[str] | None = None) -> None:
        self._runtime_models[config.id] = config
        if aliases:
            for alias in aliases:
                self._aliases[alias] = config.id

    def unregister_model(self, model_id: str) -> bool:
        if model_id not in self._runtime_models:
            return False
        del self._runtime_models[model_id]
        aliases_to_remove = [alias for alias, target in self._aliases.items() if target == model_id]
        for alias in aliases_to_remove:
            del self._aliases[alias]
        return True

    def has_runtime_model(self, model_id: str) -> bool:
        return model_id in self._runtime_models

    def has_config_model(self, model_id: str) -> bool:
        return model_id in self._config_models

    def get_runtime_model(self, model_id: str) -> ModelConfig | None:
        resolved_id = self._aliases.get(model_id, model_id)
        return self._runtime_models.get(resolved_id)

    def get_config_model(self, model_id: str) -> ModelConfig | None:
        resolved_id = self._aliases.get(model_id, model_id)
        return self._config_models.get(resolved_id)

    def get_model_candidates(self, model_id: str) -> list[ModelConfig]:
        resolved_id = self._aliases.get(model_id, model_id)
        candidates: list[ModelConfig] = []
        runtime_model = self._runtime_models.get(resolved_id)
        if runtime_model:
            candidates.append(runtime_model)
        config_model = self._config_models.get(resolved_id)
        if config_model:
            candidates.append(config_model)
        return candidates

    def _get_effective_models(self) -> dict[str, ModelConfig]:
        models = dict(self._config_models)
        models.update(self._runtime_models)
        return models

    def get_model(self, model_id: str) -> ModelConfig | None:
        if model_id in self._aliases:
            model_id = self._aliases[model_id]
        effective_models = self._get_effective_models()
        if model_id in effective_models:
            return effective_models[model_id]
        model_id_lower = model_id.lower()
        for mid, config in effective_models.items():
            if model_id_lower in mid.lower() or mid.lower() in model_id_lower:
                return config
        return None

    def get_all_models(self) -> list[ModelConfig]:
        return list(self._get_effective_models().values())

    def get_models_by_provider(self, provider: str) -> list[ModelConfig]:
        return [config for config in self._get_effective_models().values() if config.provider == provider]

    def resolve_model_pattern(self, pattern: str) -> tuple[ModelConfig | None, str | None]:
        parts = pattern.split(":", 1)
        model_id = parts[0]
        thinking_level = parts[1] if len(parts) > 1 else None
        return (self.get_model(model_id), thinking_level)

    def refresh(self) -> None:
        self._config_models.clear()
        self._runtime_models.clear()
        self._aliases.clear()
        self._load_from_json_config()


_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def register_model(config: ModelConfig, aliases: list[str] | None = None) -> None:
    get_registry().register_model(config, aliases)


def get_model(model_id: str) -> ModelConfig | None:
    return get_registry().get_model(model_id)
