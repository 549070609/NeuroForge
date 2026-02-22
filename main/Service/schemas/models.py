"""
Model Config Schemas - API 请求和响应模型

定义模型配置相关的 API 数据结构。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ==================== Enums ====================


class ProviderType(str, Enum):
    """Provider 类型"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE = "azure"
    BEDROCK = "bedrock"
    CUSTOM = "custom"


class ApiType(str, Enum):
    """API 类型"""

    ANTHROPIC_MESSAGES = "anthropic-messages"
    OPENAI_COMPLETIONS = "openai-completions"
    OPENAI_RESPONSES = "openai-responses"
    GOOGLE_GENERATIVE_AI = "google-generative-ai"
    BEDROCK_CONVERSE_STREAM = "bedrock-converse-stream"
    CUSTOM = "custom"


# ==================== Model Config Schemas ====================


class ModelConfigBase(BaseModel):
    """模型配置基础字段"""

    name: str = Field(description="显示名称")
    provider: ProviderType = Field(description="提供商类型")
    api_type: ApiType = Field(description="API 类型")

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


class ModelConfigCreate(ModelConfigBase):
    """模型配置创建请求"""

    id: str = Field(description="模型 ID (唯一标识)")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("模型 ID 不能为空")
        # 允许字母、数字、连字符、下划线、点
        import re

        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError("模型 ID 只能包含字母、数字、点、连字符和下划线")
        return v


class ModelConfigUpdate(BaseModel):
    """模型配置更新请求"""

    name: str | None = Field(default=None, description="显示名称")
    provider: ProviderType | None = Field(default=None, description="提供商类型")
    api_type: ApiType | None = Field(default=None, description="API 类型")

    supports_vision: bool | None = Field(default=None, description="是否支持图像")
    supports_tools: bool | None = Field(default=None, description="是否支持工具调用")
    supports_streaming: bool | None = Field(default=None, description="是否支持流式")

    context_window: int | None = Field(default=None, description="上下文窗口大小")
    max_output_tokens: int | None = Field(default=None, description="最大输出 tokens")

    cost_input: float | None = Field(default=None, description="输入成本/百万 tokens")
    cost_output: float | None = Field(default=None, description="输出成本/百万 tokens")
    cost_cache_read: float | None = Field(default=None, description="缓存读取成本/百万 tokens")
    cost_cache_write: float | None = Field(default=None, description="缓存写入成本/百万 tokens")

    base_url: str | None = Field(default=None, description="API 基础 URL")
    api_key_env: str | None = Field(default=None, description="API Key 环境变量名")

    extra: dict[str, Any] | None = Field(default=None, description="额外配置")


class ModelConfigResponse(BaseModel):
    """模型配置响应"""

    id: str = Field(description="模型 ID")
    name: str = Field(description="显示名称")
    provider: str = Field(description="提供商类型")
    api_type: str = Field(description="API 类型")

    supports_vision: bool = Field(description="是否支持图像")
    supports_tools: bool = Field(description="是否支持工具调用")
    supports_streaming: bool = Field(description="是否支持流式")

    context_window: int = Field(description="上下文窗口大小")
    max_output_tokens: int = Field(description="最大输出 tokens")

    cost_input: float = Field(description="输入成本/百万 tokens")
    cost_output: float = Field(description="输出成本/百万 tokens")
    cost_cache_read: float = Field(description="缓存读取成本/百万 tokens")
    cost_cache_write: float = Field(description="缓存写入成本/百万 tokens")

    base_url: str | None = Field(description="API 基础 URL")
    api_key_env: str = Field(description="API Key 环境变量名")

    extra: dict[str, Any] = Field(description="额外配置")

    is_builtin: bool = Field(default=False, description="是否为内置模型")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class ModelConfigListResponse(BaseModel):
    """模型配置列表响应"""

    models: list[ModelConfigResponse] = Field(description="模型列表")
    total: int = Field(description="总数")
    providers: list[str] = Field(default_factory=list, description="提供商列表")


class ModelConfigStatsResponse(BaseModel):
    """模型配置统计响应"""

    total_models: int = Field(description="模型总数")
    builtin_models: int = Field(description="内置模型数")
    custom_models: int = Field(description="自定义模型数")
    by_provider: dict[str, int] = Field(description="按提供商统计")


# ==================== Provider Info Schemas ====================


class ChineseProviderInfo(BaseModel):
    """国产 LLM 提供商信息"""

    vendor: str = Field(description="厂商标识")
    vendor_name: str = Field(description="厂商名称")
    models: list[str] = Field(description="支持的模型列表")
    default_model: str = Field(description="默认模型")
    api_key_env: str = Field(description="API Key 环境变量名")
    base_url: str = Field(description="API 基础 URL")
    description: str = Field(default="", description="厂商描述")


class ChineseProviderListResponse(BaseModel):
    """国产 LLM 提供商列表响应"""

    providers: list[ChineseProviderInfo] = Field(description="提供商列表")
    total: int = Field(description="总数")
