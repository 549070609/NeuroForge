"""
会话持久化系统 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.plugins.integration.persistence.persistence
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 旧: from pyagentforge.core.persistence import SessionPersistence, SessionManager
- 新: from pyagentforge.plugins.integration.persistence.persistence import SessionPersistence, SessionManager
"""

# 重导出所有内容
from pyagentforge.plugins.integration.persistence.persistence import (
    SessionMetadata,
    SessionState,
    SessionSummary,
    SessionSnapshot,
    SessionPersistence,
    SessionManager,
)

__all__ = [
    "SessionMetadata",
    "SessionState",
    "SessionSummary",
    "SessionSnapshot",
    "SessionPersistence",
    "SessionManager",
]

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core.persistence is deprecated. "
    "Use pyagentforge.plugins.integration.persistence.persistence instead.",
    DeprecationWarning,
    stacklevel=2,
)
