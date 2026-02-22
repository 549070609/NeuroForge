"""
任务数据模型

存储定时任务和事件触发任务
"""

from typing import Any

from sqlalchemy import JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from pyagentforge.models.base import Base


class TaskModel(Base):
    """任务模型"""

    # 关联的 Agent ID
    agent_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
    )

    # 任务名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 任务描述
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 任务类型
    task_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # cron, interval, event, webhook

    # 触发配置
    trigger_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # 任务输入
    task_input: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )  # pending, running, completed, failed, paused

    # 最后执行时间
    last_run_at: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # 下次执行时间
    next_run_at: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # 最后执行结果
    last_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 是否启用
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )


from sqlalchemy import String  # noqa: E402
