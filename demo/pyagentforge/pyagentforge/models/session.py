"""
会话数据模型

存储 Agent 会话信息
"""

from typing import Any

from sqlalchemy import JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from pyagentforge.models.base import Base


class SessionModel(Base):
    """会话模型"""

    # 关联的 Agent ID
    agent_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
    )

    # 会话状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="idle",
        nullable=False,
    )  # idle, active, processing, completed, error

    # 消息历史 (JSON 格式)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # 元数据
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    # 最后一条用户消息
    last_user_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 最后一条助手消息
    last_assistant_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Token 使用统计
    total_input_tokens: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    total_output_tokens: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )


# 为了解决 SQLAlchemy 的类型问题，需要导入 String
from sqlalchemy import String  # noqa: E402
