"""
代理管理模块

包含代理类型定义、代理配置等
"""

from pyagentforge.agents.types import AGENT_TYPES, AgentType
from pyagentforge.agents.config import AgentConfig

__all__ = [
    "AGENT_TYPES",
    "AgentType",
    "AgentConfig",
]
