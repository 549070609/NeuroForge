"""
Agent 配置数据模型

存储 Agent 配置信息
"""

from typing import Any

from sqlalchemy import JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from pyagentforge.models.base import Base


class AgentModel(Base):
    """Agent 配置模型"""

    # Agent 名称
    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    # Agent 描述
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Agent 版本
    version: Mapped[str] = mapped_column(
        String(20),
        default="1.0.0",
        nullable=False,
    )

    # 系统提示词
    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 运行配置
    runtime_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # 权限配置
    permission_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # 能力配置
    capability_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )


from sqlalchemy import String  # noqa: E402
