"""
v2.x API 兼容层

确保现有代码无需修改即可升级到 v3.0

使用方式:
    # 旧代码
    from pyagentforge.core.events import EventBus, EventType

    # 新代码 (推荐)
    from pyagentforge.plugins.integration.events.events import EventBus, EventType

    # 兼容层 (过渡期)
    from pyagentforge.compat.v2.events import EventBus, EventType
"""

__all__ = ["events", "failover"]
