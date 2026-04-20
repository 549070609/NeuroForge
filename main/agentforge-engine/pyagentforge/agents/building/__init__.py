"""
Agent 构建层

提供声明式 Agent 定义、流畅 API、工厂模式和热插拔加载能力
"""

from pyagentforge.agents.building.schema import (
    AgentIdentity,
    AgentSchema,
    BehaviorDefinition,
    CapabilityDefinition,
    DependencyDefinition,
    ExecutionLimits,
    MemoryConfiguration,
    ModelConfiguration,
)
from pyagentforge.agents.building.builder import AgentBuilder, AgentTemplate
from pyagentforge.agents.building.factory import AgentFactory, AgentPool, InstanceState
from pyagentforge.agents.building.loader import AgentLoadError, AgentLoader, LoadedAgent, LoadState

__all__ = [
    # Schema
    "AgentIdentity",
    "ModelConfiguration",
    "CapabilityDefinition",
    "BehaviorDefinition",
    "ExecutionLimits",
    "DependencyDefinition",
    "MemoryConfiguration",
    "AgentSchema",
    # Builder
    "AgentBuilder",
    "AgentTemplate",
    # Factory
    "AgentFactory",
    "AgentPool",
    "InstanceState",
    # Loader
    "AgentLoader",
    "LoadedAgent",
    "LoadState",
    "AgentLoadError",
]
