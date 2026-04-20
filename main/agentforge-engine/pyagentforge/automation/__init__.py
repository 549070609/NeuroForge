"""
Automation Module - 自动化模块

支持定时任务和事件驱动的 Agent 执行。

核心组件:
- TriggerType: 触发类型枚举
- AutomationTask: 自动化任务
- AutomationManager: 自动化管理器
"""

from pyagentforge.automation.scheduler import AutomationManager
from pyagentforge.automation.task import AutomationTask, TriggerType

__all__ = [
    "TriggerType",
    "AutomationTask",
    "AutomationManager",
]
