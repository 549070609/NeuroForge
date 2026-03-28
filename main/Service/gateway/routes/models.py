"""
Model Config API Routes - 模型配置相关的 REST API 端点

提供:
- 模型配置 CRUD 操作
- 模型统计信息
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...schemas.models import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigListResponse,
    ModelConfigStatsResponse,
    ModelConfigUpdate,
)
from ...services.model_config_service import ModelConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])


# ==================== 依赖注入 ====================


def get_model_config_service() -> ModelConfigService:
    """获取 ModelConfigService 实例"""
    from ...core.registry import ServiceRegistry

    registry = ServiceRegistry()
    service = registry.get("model_config")
    if service is None:
        # 如果服务未注册，创建一个临时实例
        service = ModelConfigService(registry)
    return service


# ==================== Model Config CRUD ====================


@router.get("", response_model=ModelConfigListResponse)
async def list_models(
    provider: Annotated[str | None, Query(description="Filter by provider")] = None,
    supports_vision: Annotated[
        bool | None, Query(description="Filter by vision support")
    ] = None,
    supports_tools: Annotated[
        bool | None, Query(description="Filter by tools support")
    ] = None,
    is_builtin: Annotated[bool | None, Query(description="Filter builtin models")] = None,
) -> ModelConfigListResponse:
    """
    列出所有模型配置

    - **provider**: 可选，按提供商过滤 (anthropic/openai/google/custom)
    - **supports_vision**: 可选，按是否支持图像过滤
    - **supports_tools**: 可选，按是否支持工具调用过滤
    - **is_builtin**: 可选，兼容字段；当前始终为 false
    """
    service = get_model_config_service()
    models = service.list_models(
        provider=provider,
        supports_vision=supports_vision,
        supports_tools=supports_tools,
        is_builtin=is_builtin,
    )

    # 获取所有提供商
    providers = list(set(m.provider for m in models))

    return ModelConfigListResponse(
        models=models,
        total=len(models),
        providers=providers,
    )


@router.get("/stats", response_model=ModelConfigStatsResponse)
async def get_model_stats() -> ModelConfigStatsResponse:
    """获取模型配置统计信息"""
    service = get_model_config_service()
    return service.get_stats()


@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(model_id: str) -> ModelConfigResponse:
    """
    获取单个模型配置

    - **model_id**: 模型 ID (如 'default', 'custom-chat')
    """
    service = get_model_config_service()
    model = service.get_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model not found: {model_id}",
        )
    return model


@router.post(
    "", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED
)
async def create_model(request: ModelConfigCreate) -> ModelConfigResponse:
    """
    创建新的模型配置

    请求体包含:
    - **id**: 模型 ID (唯一标识)
    - **name**: 显示名称
    - **provider**: 提供商标识字符串
    - **api_type**: API 类型
    - **supports_vision**: 是否支持图像
    - **supports_tools**: 是否支持工具调用
    - **context_window**: 上下文窗口大小
    - **max_output_tokens**: 最大输出 tokens
    - **cost_input/output**: 成本配置
    - **base_url**: API 基础 URL (自定义模型需要)
    - **api_key_env**: API Key 环境变量名
    - **extra**: 额外配置（如自定义头、路由参数等）
    """
    service = get_model_config_service()
    try:
        model = service.create_model(request)
        return model
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch("/{model_id}", response_model=ModelConfigResponse)
async def update_model(
    model_id: str,
    request: ModelConfigUpdate,
) -> ModelConfigResponse:
    """
    更新模型配置

    - **model_id**: 要更新的模型 ID

    请求体可包含任意可更新字段:
    - **name**: 显示名称
    - **supports_vision**: 是否支持图像
    - **supports_tools**: 是否支持工具调用
    - **context_window**: 上下文窗口大小
    - **cost_input/output**: 成本配置
    - **base_url**: API 基础 URL
    - **extra**: 额外配置
    """
    service = get_model_config_service()
    try:
        model = service.update_model(model_id, request)
        return model
    except ValueError as e:
        if "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{model_id}")
async def delete_model(model_id: str) -> dict[str, str]:
    """
    删除模型配置

    - **model_id**: 要删除的模型 ID

    注意: 当前模型均为配置模型，可直接删除
    """
    service = get_model_config_service()
    try:
        success = service.delete_model(model_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model not found: {model_id}",
            )
        return {"status": "ok", "message": f"Model {model_id} deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


