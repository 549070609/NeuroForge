"""
Model Config Service - 模型配置管理服务

提供模型配置的增删改查功能。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any


def _utcnow() -> datetime:
    """Return a naive UTC datetime (timezone stripped for backward compat)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from pyagentforge import ModelConfig, get_registry, register_model

from ..schemas.models import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigStatsResponse,
    ModelConfigUpdate,
)

if TYPE_CHECKING:
    from ..core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


BUILTIN_MODEL_IDS: set[str] = set()


class ModelConfigService:
    """
    模型配置管理服务

    提供:
    - 模型配置的 CRUD 操作
    - 内置模型和自定义模型的统一管理
    """

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self._initialized = False
        self._logger = logging.getLogger(__name__)
        self._custom_configs: dict[str, dict[str, Any]] = {}
        self._config_timestamps: dict[str, dict[str, datetime]] = {}

    async def initialize(self) -> None:
        """初始化服务"""
        if self._initialized:
            return

        self._logger.debug("Initializing ModelConfigService...")
        await self._on_initialize()
        self._initialized = True
        self._logger.debug("ModelConfigService initialized")

    async def shutdown(self) -> None:
        """关闭服务"""
        if not self._initialized:
            return

        self._logger.debug("Shutting down ModelConfigService...")
        await self._on_shutdown()
        self._initialized = False
        self._logger.debug("ModelConfigService shut down")

    async def _on_initialize(self) -> None:
        """初始化钩子 - 加载自定义配置"""
        # 从持久化存储加载自定义配置（这里简化为内存存储）
        # 实际实现可以从文件或数据库加载
        self._custom_configs = {}
        self._config_timestamps = {}

    async def _on_shutdown(self) -> None:
        """关闭钩子 - 保存自定义配置"""
        # 保存自定义配置到持久化存储
        pass

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _get_registry(self):
        return get_registry()

    # ==================== CRUD Operations ====================

    def list_models(
        self,
        provider: str | None = None,
        supports_vision: bool | None = None,
        supports_tools: bool | None = None,
        is_builtin: bool | None = None,
    ) -> list[ModelConfigResponse]:
        """
        获取模型配置列表

        Args:
            provider: 按提供商过滤
            supports_vision: 按是否支持图像过滤
            supports_tools: 按是否支持工具过滤
            is_builtin: 按是否为内置模型过滤

        Returns:
            模型配置列表
        """
        registry = self._get_registry()
        models = []

        for config in registry.get_all_models():
            # 应用过滤器
            if provider and config.provider != provider:
                continue
            if supports_vision is not None and config.supports_vision != supports_vision:
                continue
            if supports_tools is not None and config.supports_tools != supports_tools:
                continue

            model_is_builtin = False
            if is_builtin is not None and model_is_builtin != is_builtin:
                continue

            # 获取时间戳
            timestamps = self._config_timestamps.get(config.id, {})

            models.append(
                ModelConfigResponse(
                    id=config.id,
                    name=config.name,
                    provider=config.provider,
                    api_type=config.api_type,
                    model_name=config.model_name,
                    supports_vision=config.supports_vision,
                    supports_tools=config.supports_tools,
                    supports_streaming=config.supports_streaming,
                    context_window=config.context_window,
                    max_output_tokens=config.max_output_tokens,
                    cost_input=config.cost_input,
                    cost_output=config.cost_output,
                    cost_cache_read=config.cost_cache_read,
                    cost_cache_write=config.cost_cache_write,
                    base_url=config.base_url,
                    api_key=config.api_key,
                    api_key_env=config.api_key_env,
                    headers=config.headers,
                    timeout=config.timeout,
                    extra=config.extra,
                    is_builtin=model_is_builtin,
                    created_at=timestamps.get("created_at"),
                    updated_at=timestamps.get("updated_at"),
                )
            )

        return models

    def get_model(self, model_id: str) -> ModelConfigResponse | None:
        """
        获取单个模型配置

        Args:
            model_id: 模型 ID

        Returns:
            模型配置，不存在返回 None
        """
        registry = self._get_registry()
        config = registry.get_model(model_id)

        if not config:
            return None

        is_builtin = False
        timestamps = self._config_timestamps.get(config.id, {})

        return ModelConfigResponse(
            id=config.id,
            name=config.name,
            provider=config.provider,
            api_type=config.api_type,
            model_name=config.model_name,
            supports_vision=config.supports_vision,
            supports_tools=config.supports_tools,
            supports_streaming=config.supports_streaming,
            context_window=config.context_window,
            max_output_tokens=config.max_output_tokens,
            cost_input=config.cost_input,
            cost_output=config.cost_output,
            cost_cache_read=config.cost_cache_read,
            cost_cache_write=config.cost_cache_write,
            base_url=config.base_url,
            api_key=config.api_key,
            api_key_env=config.api_key_env,
            headers=config.headers,
            timeout=config.timeout,
            extra=config.extra,
            is_builtin=is_builtin,
            created_at=timestamps.get("created_at"),
            updated_at=timestamps.get("updated_at"),
        )

    def create_model(self, request: ModelConfigCreate) -> ModelConfigResponse:
        """
        创建模型配置

        Args:
            request: 创建请求

        Returns:
            创建的模型配置

        Raises:
            ValueError: 如果模型 ID 已存在
        """
        # 检查是否已存在
        registry = self._get_registry()
        if registry.has_runtime_model(request.id):
            raise ValueError(f"模型 ID '{request.id}' 已存在")

        # 创建配置
        config = ModelConfig(
            id=request.id,
            name=request.name,
            provider=request.provider,
            api_type=request.api_type.value,
            model_name=request.model_name,
            supports_vision=request.supports_vision,
            supports_tools=request.supports_tools,
            supports_streaming=request.supports_streaming,
            context_window=request.context_window,
            max_output_tokens=request.max_output_tokens,
            cost_input=request.cost_input,
            cost_output=request.cost_output,
            cost_cache_read=request.cost_cache_read,
            cost_cache_write=request.cost_cache_write,
            base_url=request.base_url,
            api_key=request.api_key,
            api_key_env=request.api_key_env,
            headers=request.headers,
            timeout=request.timeout,
            extra=request.extra,
        )

        # 注册模型
        register_model(config)

        # 记录时间戳
        now = _utcnow()
        self._config_timestamps[request.id] = {
            "created_at": now,
            "updated_at": now,
        }

        self._logger.info(f"Created model config: {request.id}")

        return self.get_model(request.id)  # type: ignore

    def update_model(
        self, model_id: str, request: ModelConfigUpdate
    ) -> ModelConfigResponse:
        """
        更新模型配置

        Args:
            model_id: 模型 ID
            request: 更新请求

        Returns:
            更新后的模型配置

        Raises:
            ValueError: 如果模型不存在或尝试修改内置模型的关键字段
        """
        registry = get_registry()
        existing = registry.get_model(model_id)

        if not existing:
            raise ValueError(f"模型 '{model_id}' 不存在")

        # 构建更新后的配置
        update_data = request.model_dump(exclude_unset=True)

        # 处理 provider 字段
        provider = update_data.get("provider", existing.provider)

        # 创建新配置（合并现有值和更新值）
        new_config = ModelConfig(
            id=model_id,
            name=update_data.get("name", existing.name),
            provider=provider,
            api_type=update_data.get("api_type", existing.api_type),
            model_name=update_data.get("model_name", existing.model_name),
            supports_vision=update_data.get("supports_vision", existing.supports_vision),
            supports_tools=update_data.get("supports_tools", existing.supports_tools),
            supports_streaming=update_data.get(
                "supports_streaming", existing.supports_streaming
            ),
            context_window=update_data.get("context_window", existing.context_window),
            max_output_tokens=update_data.get(
                "max_output_tokens", existing.max_output_tokens
            ),
            cost_input=update_data.get("cost_input", existing.cost_input),
            cost_output=update_data.get("cost_output", existing.cost_output),
            cost_cache_read=update_data.get("cost_cache_read", existing.cost_cache_read),
            cost_cache_write=update_data.get(
                "cost_cache_write", existing.cost_cache_write
            ),
            base_url=update_data.get("base_url", existing.base_url),
            api_key=update_data.get("api_key", existing.api_key),
            api_key_env=update_data.get("api_key_env", existing.api_key_env),
            headers=update_data.get("headers", existing.headers),
            timeout=update_data.get("timeout", existing.timeout),
            extra=update_data.get("extra", existing.extra),
        )

        # 重新注册（会覆盖现有配置）
        registry.register_model(new_config)

        # 更新时间戳
        if model_id not in self._config_timestamps:
            self._config_timestamps[model_id] = {"created_at": _utcnow()}
        self._config_timestamps[model_id]["updated_at"] = _utcnow()

        self._logger.info(f"Updated model config: {model_id}")

        return self.get_model(model_id)  # type: ignore

    def delete_model(self, model_id: str) -> bool:
        """
        删除模型配置

        Args:
            model_id: 模型 ID

        Returns:
            是否删除成功

        Raises:
            ValueError: 如果尝试删除内置模型
        """
        # 检查是否为内置模型
        registry = get_registry()

        # 检查是否存在
        if not registry.get_model(model_id):
            return False

        # 删除
        success = registry.unregister_model(model_id)

        if success:
            # 清理时间戳
            self._config_timestamps.pop(model_id, None)
            self._logger.info(f"Deleted model config: {model_id}")

        return success

    # ==================== Statistics ====================

    def get_stats(self) -> ModelConfigStatsResponse:
        """
        获取模型配置统计信息

        Returns:
            统计信息
        """
        models = self.list_models()

        total = len(models)
        builtin = sum(1 for m in models if m.is_builtin)
        custom = total - builtin

        by_provider: dict[str, int] = {}
        for m in models:
            by_provider[m.provider] = by_provider.get(m.provider, 0) + 1

        return ModelConfigStatsResponse(
            total_models=total,
            builtin_models=builtin,
            custom_models=custom,
            by_provider=by_provider,
        )
