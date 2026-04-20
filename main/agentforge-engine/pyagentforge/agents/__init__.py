"""
Agent Management Module.

Unified home for everything that describes *what an agent is*:

- `agents.config` / `agents.types` / `agents.metadata` / `agents.registry` —
  runtime registration, types, metadata, and dynamic prompt assembly.
- `agents.building` — declarative schema, builder, factory and loader.
- `agents.prompts` — capability-aware prompt variants and registry.
- `agents.skills` — skill definitions, parsers, loaders, registry.
- `agents.commands` — custom slash-commands, parser, registry, tool.
"""

from pyagentforge.agents.config import AgentConfig, PermissionConfig, RuntimeConfig
from pyagentforge.agents.dynamic_prompt_builder import (
    DynamicPromptBuilder,
    PromptContext,
    create_prompt_context,
)
from pyagentforge.agents.metadata import (
    BUILTIN_AGENTS,
    AgentCategory,
    AgentCost,
    AgentMetadata,
    get_agent_metadata,
    get_agent_selection_table,
    get_agents_by_category,
    get_agents_by_cost,
    get_background_capable_agents,
    get_readonly_agents,
)
from pyagentforge.agents.registry import (
    AgentInstance,
    AgentRegistry,
    get_agent_registry,
)
from pyagentforge.agents.types import AGENT_TYPES, AgentType, get_agent_type_config

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
    # Dynamic Prompt Builder
    "DynamicPromptBuilder",
    "PromptContext",
    "create_prompt_context",
]
