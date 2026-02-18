"""
Agent Management Module

Contains agent types, configurations, and registry.
"""

from pyagentforge.agents.types import AGENT_TYPES, AgentType, get_agent_type_config
from pyagentforge.agents.config import AgentConfig, RuntimeConfig, PermissionConfig
from pyagentforge.agents.metadata import (
    AgentCategory,
    AgentCost,
    AgentMetadata,
    BUILTIN_AGENTS,
    get_agent_metadata,
    get_agents_by_category,
    get_agents_by_cost,
    get_readonly_agents,
    get_background_capable_agents,
    get_agent_selection_table,
)
from pyagentforge.agents.registry import (
    AgentRegistry,
    AgentInstance,
    get_agent_registry,
)

__all__ = [
    # Types
    "AgentType",
    "AGENT_TYPES",
    "get_agent_type_config",
    # Config
    "AgentConfig",
    "RuntimeConfig",
    "PermissionConfig",
    # Metadata
    "AgentCategory",
    "AgentCost",
    "AgentMetadata",
    "BUILTIN_AGENTS",
    "get_agent_metadata",
    "get_agents_by_category",
    "get_agents_by_cost",
    "get_readonly_agents",
    "get_background_capable_agents",
    "get_agent_selection_table",
    # Registry
    "AgentRegistry",
    "AgentInstance",
    "get_agent_registry",
]
