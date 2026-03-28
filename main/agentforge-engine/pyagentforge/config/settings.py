"""
配置管理模块

使用 pydantic-settings 管理应用配置
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============ LLM 配置 ============
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    default_model: str = Field(
        default="default",
        description="默认使用的模型",
    )
    max_tokens: int = Field(default=4096, description="最大输出 Token")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="温度参数")

    # ============ 服务配置 ============
    host: str = Field(default="0.0.0.0", description="服务监听地址")
    port: int = Field(default=8000, ge=1, le=65535, description="服务监听端口")
    debug: bool = Field(default=False, description="调试模式")

    # ============ 数据库配置 ============
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/pyagentforge.db",
        description="数据库连接 URL",
    )

    # ============ 安全配置 ============
    jwt_secret_key: str = Field(
        default="change-me-in-production",
        description="JWT 签名密钥",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT 算法")
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access Token 过期时间(分钟)",
    )

    # ============ 存储配置 ============
    skills_dir: Path = Field(
        default=Path("./data/skills"),
        description="技能目录",
    )
    commands_dir: Path = Field(
        default=Path("./data/commands"),
        description="命令目录",
    )
    data_dir: Path = Field(
        default=Path("./data"),
        description="数据目录",
    )

    # ============ 日志配置 ============
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志级别",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="日志格式",
    )

    # ============ Agent 配置 ============
    default_timeout: int = Field(default=120, description="默认超时时间(秒)")
    tool_timeout: int = Field(default=60, description="工具执行超时时间(秒)")
    max_subagent_depth: int = Field(default=3, description="子代理最大递归深度")
    max_context_messages: int = Field(default=100, description="最大上下文消息数")
    max_tool_output_length: int = Field(
        default=50000,
        description="工具输出最大长度",
    )

    # ============ 上下文压缩配置 ============
    compaction_enabled: bool = Field(default=True, description="是否启用上下文压缩")
    compaction_reserve_tokens: int = Field(
        default=8000,
        description="压缩时预留的 tokens",
    )
    compaction_keep_recent_tokens: int = Field(
        default=4000,
        description="保留最近消息的 tokens",
    )
    compaction_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=1.0,
        description="触发压缩的上下文使用率阈值",
    )
    max_context_tokens: int = Field(
        default=200000,
        description="最大上下文 tokens",
    )

    # ============ 思考级别配置 ============
    default_thinking_level: str = Field(
        default="off",
        description="默认思考级别 (off/minimal/low/medium/high/xhigh)",
    )
    thinking_budget_tokens: int | None = Field(
        default=None,
        description="思考 token 预算 (None 表示自动)",
    )

    def ensure_directories(self) -> None:
        """确保必要目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.commands_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    settings = Settings()
    settings.ensure_directories()
    return settings
