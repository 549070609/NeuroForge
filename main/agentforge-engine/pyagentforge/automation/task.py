"""
Automation Task - 自动化任务定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TriggerType(str, Enum):
    """触发类型"""
    TIME = "time"       # 定时触发 (Cron)
    EVENT = "event"     # 事件触发
    WEBHOOK = "webhook" # Webhook 触发


@dataclass
class AutomationTask:
    """
    自动化任务

    Attributes:
        id: 任务唯一标识
        name: 任务名称
        trigger_type: 触发类型
        trigger_config: 触发器配置
        action: Agent 执行的 prompt 或函数名
        enabled: 是否启用
        last_run: 最后执行时间
        next_run: 下次执行时间
        run_count: 执行次数
        metadata: 元数据
    """
    id: str
    name: str
    trigger_type: TriggerType
    trigger_config: dict[str, Any]
    action: str
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "trigger_type": self.trigger_type.value,
            "trigger_config": self.trigger_config,
            "action": self.action,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
        }
