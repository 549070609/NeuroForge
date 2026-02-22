"""
Agent Registry

Manages agent registration, discovery, and tool filtering.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from pyagentforge.agents.metadata import (
    AgentCategory,
    AgentCost,
    AgentMetadata,
    BUILTIN_AGENTS,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentInstance:
    """Running agent instance"""

    id: str
    agent_type: str
    status: str = "idle"
    session_id: str = ""
    created_at: str = ""
    metadata: AgentMetadata | None = None


class AgentRegistry:
    """
    Agent Registry

    Manages agent types, metadata, and provides lookup functionality.
    """

    def __init__(self):
        """Initialize agent registry"""
        self._agents: dict[str, AgentMetadata] = dict(BUILTIN_AGENTS)
        self._tool_registry: Any = None  # Set by set_tool_registry
        self._instances: dict[str, AgentInstance] = {}

    def register(self, agent: AgentMetadata) -> None:
        """
        Register a new agent type

        Args:
            agent: Agent metadata
        """
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister an agent type

        Args:
            name: Agent name

        Returns:
            True if unregistered, False if not found
        """
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Unregistered agent: {name}")
            return True
        return False

    def get(self, name: str) -> AgentMetadata | None:
        """
        Get agent by name

        Args:
            name: Agent name

        Returns:
            AgentMetadata or None
        """
        return self._agents.get(name)

    def list_all(self) -> list[AgentMetadata]:
        """Get all registered agents"""
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        """Get all agent names"""
        return list(self._agents.keys())

    def get_by_category(self, category: AgentCategory) -> list[AgentMetadata]:
        """
        Get agents by category

        Args:
            category: Agent category

        Returns:
            List of matching agents
        """
        return [a for a in self._agents.values() if a.category == category]

    def get_by_cost(self, cost: AgentCost) -> list[AgentMetadata]:
        """
        Get agents by cost tier

        Args:
            cost: Cost tier

        Returns:
            List of matching agents
        """
        return [a for a in self._agents.values() if a.cost == cost]

    def get_readonly(self) -> list[AgentMetadata]:
        """Get all read-only agents"""
        return [a for a in self._agents.values() if a.is_readonly]

    def get_background_capable(self) -> list[AgentMetadata]:
        """Get all agents that support background execution"""
        return [a for a in self._agents.values() if a.supports_background]

    def set_tool_registry(self, tool_registry: Any) -> None:
        """
        Set the tool registry for filtering

        Args:
            tool_registry: Tool registry instance
        """
        self._tool_registry = tool_registry

    def get_available_tools(self, agent_name: str) -> list[str]:
        """
        Get available tools for an agent

        Args:
            agent_name: Agent name

        Returns:
            List of available tool names
        """
        agent = self.get(agent_name)
        if agent is None:
            return []

        if "*" in agent.tools:
            # All tools available
            if self._tool_registry is not None:
                return self._tool_registry.list_names()
            return []

        # Filter tools
        return agent.tools

    def match_agent(self, task_description: str) -> AgentMetadata | None:
        """
        Match the best agent for a task description

        Uses keyword matching on key_trigger patterns

        Args:
            task_description: Task description

        Returns:
            Best matching agent or None
        """
        import re

        task_lower = task_description.lower()
        best_match = None
        best_score = 0

        for agent in self._agents.values():
            score = 0

            # Check key trigger pattern
            if agent.key_trigger:
                if re.search(agent.key_trigger, task_lower, re.IGNORECASE):
                    score += 10

            # Check use_when keywords
            for keyword in agent.use_when:
                if keyword.lower() in task_lower:
                    score += 2

            # Avoid agents whose avoid_when patterns match
            for keyword in agent.avoid_when:
                if keyword.lower() in task_lower:
                    score -= 5

            if score > best_score:
                best_score = score
                best_match = agent

        return best_match

    def register_instance(self, instance: AgentInstance) -> None:
        """Register a running agent instance"""
        self._instances[instance.id] = instance

    def unregister_instance(self, instance_id: str) -> None:
        """Unregister an agent instance"""
        if instance_id in self._instances:
            del self._instances[instance_id]

    def get_instance(self, instance_id: str) -> AgentInstance | None:
        """Get agent instance by ID"""
        return self._instances.get(instance_id)

    def list_active_instances(self) -> list[AgentInstance]:
        """Get all active agent instances"""
        return [i for i in self._instances.values() if i.status == "running"]

    def get_concurrency_usage(self, agent_name: str) -> int:
        """
        Get current concurrency usage for an agent type

        Args:
            agent_name: Agent name

        Returns:
            Number of running instances
        """
        return sum(
            1
            for i in self._instances.values()
            if i.agent_type == agent_name and i.status == "running"
        )

    def can_spawn(self, agent_name: str) -> bool:
        """
        Check if we can spawn another instance of an agent

        Args:
            agent_name: Agent name

        Returns:
            True if we can spawn
        """
        agent = self.get(agent_name)
        if agent is None:
            return False

        current = self.get_concurrency_usage(agent_name)
        return current < agent.max_concurrent

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry to dictionary"""
        return {
            "agents": {name: agent.to_dict() for name, agent in self._agents.items()},
            "active_instances": len(self.list_active_instances()),
        }

    # ==================== 构建层扩展方法 ====================

    def register_schema(self, schema: "AgentSchema") -> None:
        """
        从 Schema 注册 Agent

        Args:
            schema: AgentSchema 实例
        """
        metadata = schema.to_agent_metadata()
        self.register(metadata)

    def find_by_capability(self, capability: str) -> list[AgentMetadata]:
        """
        按能力查找 Agent（工具名）

        Args:
            capability: 工具名或能力

        Returns:
            匹配的 Agent 列表
        """
        results = []
        for agent in self._agents.values():
            # 检查是否包含该工具
            if "*" in agent.tools or capability in agent.tools:
                results.append(agent)
        return results

    def find_by_tags(self, tags: list[str]) -> list[AgentMetadata]:
        """
        按标签查找 Agent

        Args:
            tags: 标签列表

        Returns:
            匹配的 Agent 列表
        """
        results = []
        for agent in self._agents.values():
            # 检查是否包含任意标签
            if any(tag in agent.tags for tag in tags):
                results.append(agent)
        return results

    def find_best_for_task(self, task_description: str) -> AgentMetadata | None:
        """
        智能匹配最适合任务的 Agent（增强版 match_agent）

        Args:
            task_description: 任务描述

        Returns:
            最佳匹配的 Agent 或 None
        """
        import re

        task_lower = task_description.lower()
        candidates = []

        for agent in self._agents.values():
            score = 0

            # 1. 检查 key_trigger 模式（权重 10）
            if agent.key_trigger:
                if re.search(agent.key_trigger, task_lower, re.IGNORECASE):
                    score += 10

            # 2. 检查 use_when 关键词（权重 2）
            for keyword in agent.use_when:
                if keyword.lower() in task_lower:
                    score += 2

            # 3. 检查 avoid_when 模式（负权重 -5）
            for keyword in agent.avoid_when:
                if keyword.lower() in task_lower:
                    score -= 5

            # 4. 检查标签匹配（权重 3）
            for tag in agent.tags:
                if tag.lower() in task_lower:
                    score += 3

            # 5. 检查委托触发器（权重 4）
            for trigger in agent.triggers:
                if trigger.domain.lower() in task_lower or trigger.trigger.lower() in task_lower:
                    score += 4

            # 6. 检查描述关键词（权重 1）
            if agent.description:
                desc_words = agent.description.lower().split()
                for word in desc_words:
                    if word in task_lower and len(word) > 3:
                        score += 1

            # 如果得分大于 0，加入候选列表
            if score > 0:
                candidates.append((agent, score))

        # 按得分排序，返回最高分的 Agent
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        # 如果没有匹配，返回 None
        return None


# Global registry instance
_global_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry
