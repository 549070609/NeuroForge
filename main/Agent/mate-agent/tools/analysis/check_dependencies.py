"""
检查依赖工具

检查 Agent 之间的依赖关系。
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class CheckDependenciesTool(MateAgentTool):
    """
    检查依赖工具

    检查 Agent 之间的依赖关系，包括:
    - 子Agent 依赖
    - 工具依赖
    - 命名空间依赖

    参数:
        agent_id: Agent ID (可选，不提供则检查所有)
        direction: 依赖方向 (depends_on/depended_by/all)
    """

    name = "check_dependencies"
    description = "检查 Agent 之间的依赖关系"
    category = "analysis"
    requires_confirmation = False
    timeout = 20

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "要检查的 Agent ID (可选，不提供则检查所有)"
            },
            "direction": {
                "type": "string",
                "enum": ["depends_on", "depended_by", "all"],
                "description": "依赖方向",
                "default": "all"
            }
        }
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行依赖检查

        Args:
            agent_id: Agent ID
            direction: 依赖方向

        Returns:
            依赖关系报告
        """
        agent_id = kwargs.get("agent_id")
        direction = kwargs.get("direction", "all")

        try:
            directory = self._ensure_directory()

            if agent_id:
                # 检查单个 Agent
                agent = directory.get_agent(agent_id)
                if not agent:
                    return self._format_error(f"Agent '{agent_id}' 不存在", "AGENT_NOT_FOUND")

                result = self._check_single_agent(agent, direction, directory)
            else:
                # 检查所有 Agent
                result = self._check_all_agents(directory)

            self._log_operation("check_dependencies", {
                "agent_id": agent_id,
                "direction": direction,
            })

            return self._format_success("依赖检查完成", result)

        except Exception as e:
            logger.exception("Failed to check dependencies")
            return self._format_error(f"依赖检查失败: {str(e)}", "CHECK_FAILED")

    def _check_single_agent(
        self,
        agent: Any,
        direction: str,
        directory: Any,
    ) -> dict[str, Any]:
        """
        检查单个 Agent 的依赖

        Args:
            agent: AgentInfo 实例
            direction: 依赖方向
            directory: AgentDirectory 实例

        Returns:
            依赖检查结果
        """
        result = {
            "agent_id": agent.agent_id,
            "dependencies": {},
            "issues": [],
        }

        if direction in ("depends_on", "all"):
            result["dependencies"]["depends_on"] = self._get_dependencies(agent)

        if direction in ("depended_by", "all"):
            result["dependencies"]["depended_by"] = self._get_dependents(agent, directory)

        # 检查问题
        result["issues"] = self._find_dependency_issues(
            agent,
            result["dependencies"],
            directory,
        )

        return result

    def _check_all_agents(self, directory: Any) -> dict[str, Any]:
        """
        检查所有 Agent 的依赖

        Args:
            directory: AgentDirectory 实例

        Returns:
            全局依赖检查结果
        """
        dependency_graph = {}
        all_issues = []

        for agent in directory.list_agents():
            deps = self._get_dependencies(agent)
            dependents = self._get_dependents(agent, directory)
            issues = self._find_dependency_issues(agent, {
                "depends_on": deps,
                "depended_by": dependents,
            }, directory)

            dependency_graph[agent.agent_id] = {
                "depends_on": deps,
                "depended_by": dependents,
                "issues": issues,
            }

            if issues:
                all_issues.extend([
                    {"agent_id": agent.agent_id, **issue}
                    for issue in issues
                ])

        # 检测循环依赖
        circular = self._detect_circular_dependencies(dependency_graph)
        if circular:
            all_issues.append({
                "type": "circular_dependency",
                "agents": circular,
                "message": f"检测到循环依赖: {' -> '.join(circular)}",
            })

        return {
            "dependency_graph": dependency_graph,
            "all_issues": all_issues,
            "statistics": {
                "total_agents": len(dependency_graph),
                "agents_with_dependencies": sum(
                    1 for d in dependency_graph.values()
                    if d["depends_on"]["subagents"] or d["depends_on"]["tools"]
                ),
                "total_issues": len(all_issues),
            },
        }

    def _get_dependencies(self, agent: Any) -> dict[str, list[str]]:
        """
        获取 Agent 的依赖

        Args:
            agent: AgentInfo 实例

        Returns:
            依赖信息
        """
        metadata = agent.metadata

        # 子Agent 依赖
        subagents = []
        for config in metadata.get("subagents", {}).values():
            if isinstance(config, dict):
                dep_agent = config.get("agent")
                if dep_agent:
                    subagents.append(dep_agent)

        # 工具依赖 (假设工具名可能是其他 Agent)
        tools = metadata.get("capabilities", {}).get("tools", [])
        tool_deps = []
        for tool in tools:
            if tool.startswith("use_"):
                # use_xxx 表示依赖 xxx Agent
                tool_deps.append(tool[4:])

        return {
            "subagents": subagents,
            "tools": tool_deps,
            "namespaces": self._extract_namespace_deps(metadata),
        }

    def _get_dependents(self, agent: Any, directory: Any) -> dict[str, list[str]]:
        """
        获取依赖此 Agent 的其他 Agent

        Args:
            agent: AgentInfo 实例
            directory: AgentDirectory 实例

        Returns:
            被依赖信息
        """
        agent_id = agent.agent_id
        dependents = {
            "subagents": [],
            "tools": [],
        }

        for other in directory.list_agents():
            if other.agent_id == agent_id:
                continue

            # 检查子Agent依赖
            for config in other.metadata.get("subagents", {}).values():
                if isinstance(config, dict) and config.get("agent") == agent_id:
                    dependents["subagents"].append(other.agent_id)
                    break

            # 检查工具依赖
            tools = other.metadata.get("capabilities", {}).get("tools", [])
            if f"use_{agent_id}" in tools:
                dependents["tools"].append(other.agent_id)

        return dependents

    def _extract_namespace_deps(self, metadata: dict[str, Any]) -> list[str]:
        """提取命名空间依赖"""
        namespaces = set()

        # 从子Agent配置中提取
        for config in metadata.get("subagents", {}).values():
            if isinstance(config, dict):
                agent = config.get("agent", "")
                if "/" in agent or "{}" in agent:
                    # 包含命名空间分隔符
                    parts = agent.replace("{}", "/").split("/")
                    if len(parts) > 1:
                        namespaces.add(parts[0])

        return list(namespaces)

    def _find_dependency_issues(
        self,
        agent: Any,
        dependencies: dict[str, Any],
        directory: Any,
    ) -> list[dict[str, str]]:
        """
        查找依赖问题

        Args:
            agent: AgentInfo 实例
            dependencies: 依赖信息
            directory: AgentDirectory 实例

        Returns:
            问题列表
        """
        issues = []

        # 检查子Agent是否存在
        for subagent_id in dependencies.get("depends_on", {}).get("subagents", []):
            if not directory.get_agent(subagent_id):
                issues.append({
                    "type": "missing_subagent",
                    "subagent": subagent_id,
                    "message": f"子Agent '{subagent_id}' 不存在",
                })

        # 检查自我依赖
        agent_id = agent.agent_id
        deps = dependencies.get("depends_on", {})
        if agent_id in deps.get("subagents", []):
            issues.append({
                "type": "self_dependency",
                "message": "Agent 不能依赖自身",
            })

        return issues

    def _detect_circular_dependencies(self, graph: dict[str, Any]) -> list[str] | None:
        """
        检测循环依赖

        Args:
            graph: 依赖图

        Returns:
            循环依赖路径，或 None
        """
        def dfs(node: str, visited: set[str], path: list[str]) -> list[str] | None:
            if node in path:
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]

            if node in visited:
                return None

            visited.add(node)
            path.append(node)

            # 获取依赖的子Agent
            deps = graph.get(node, {}).get("depends_on", {}).get("subagents", [])
            for dep in deps:
                result = dfs(dep, visited, path)
                if result:
                    return result

            path.pop()
            return None

        visited: set[str] = set()

        for node in graph:
            if node not in visited:
                cycle = dfs(node, visited, [])
                if cycle:
                    return cycle

        return None
