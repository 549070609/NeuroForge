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
from typing import Any

from pydantic import BaseModel, Field, field_validator

# 统一使用 kernel 层的 ModelConfig，避免两份重复定义导致的字段漂移与
# api_type 枚举不一致（插件式协议注册要求 api_type 为开放字符串）。
# 该导入是顶层导入，``kernel.model_registry`` 未反向依赖本模块顶层，
# 因此不会触发循环导入（kernel 对 config 的引用在函数内部延迟加载）。
from pyagentforge.kernel.model_registry import ModelConfig

logger = logging.getLogger(__name__)

__all__ = [
    "ModelConfig",
    "LLMConfig",
    "LLMConfigManager",
    "get_llm_config_manager",
    "get_llm_config",
]


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
    ENV_CONFIG_PATH = "LLM_CONFIG_PATH"

    def __init__(self) -> None:
        self._config: LLMConfig | None = None
        self._config_path: Path | None = None

    def _resolve_config_path(self, custom_path: str | Path | None = None) -> Path:
        """P1-9: 配置路径解析优先级 custom_path > env > 向上查找 > CWD fallback。"""
        if custom_path:
            return Path(custom_path)

        env_path = os.environ.get(self.ENV_CONFIG_PATH)
        if env_path:
            return Path(env_path)

        # 从本文件所在目录开始向上查找，再尝试 CWD
        search_roots = [Path(__file__).resolve().parent]
        try:
            search_roots.append(Path.cwd())
        except OSError:
            pass

        for root in search_roots:
            current = root
            for _ in range(5):
                candidate = current / self.DEFAULT_CONFIG_PATH
                if candidate.exists():
                    return candidate
                parent = current.parent
                if parent == current:
                    break
                current = parent

        return Path.cwd() / self.DEFAULT_CONFIG_PATH

    def load_config(self, path: str | Path | None = None) -> LLMConfig:
        self._config_path = self._resolve_config_path(path)
        path = self._config_path

        if not path.exists():
            logger.warning(f"LLM config file not found: {path}, using defaults")
            self._config = LLMConfig()
            return self._config

        try:
            with open(path, encoding="utf-8") as file:
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

    def get_provider_config(self, _provider: str) -> None:
        return None

    def get_model_config(self, model_id: str) -> ModelConfig | None:
        return self.get_config().models.get(model_id)

    def get_api_key(self, _provider: str, model_id: str | None = None) -> str | None:
        if model_id:
            model_config = self.get_model_config(model_id)
            if model_config:
                if model_config.api_key:
                    return model_config.api_key
                if model_config.api_key_env:
                    return os.environ.get(model_config.api_key_env)
        return None

    def get_base_url(self, _provider: str, model_id: str | None = None) -> str | None:
        if model_id:
            model_config = self.get_model_config(model_id)
            if model_config:
                return model_config.base_url
        return None


def get_llm_config_manager() -> LLMConfigManager:
    return LLMConfigManager()


def get_llm_config() -> LLMConfig:
    return get_llm_config_manager().get_config()
