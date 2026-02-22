"""
列出 Agent 工具

列出所有可用的 Agent。
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import MateAgentTool
from main.Agent.core import AgentOrigin

logger = logging.getLogger(__name__)


class ListAgentsTool(MateAgentTool):
    """
    列出 Agent 工具

    列出所有可用的 Agent，支持按命名空间、来源、标签过滤。

    参数:
        namespace: 过滤命名空间 (可选)
        tags: 过滤标签 (可选，满足任一即可)
        origin: 过滤来源类型 (可选)
        format: 输出格式 (simple/detailed)
    """

    name = "list_agents"
    description = "列出所有可用的 Agent"
    category = "crud"
    requires_confirmation = False
    timeout = 10

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "namespace": {
                "type": "string",
                "description": "过滤命名空间"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "过滤标签 (满足任一即可)"
            },
            "origin": {
                "type": "string",
                "enum": ["public", "namespace", "bundled", "config"],
                "description": "过滤来源类型"
            },
            "format": {
                "type": "string",
                "enum": ["simple", "detailed"],
                "description": "输出格式",
                "default": "simple"
            }
        }
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行列出 Agent

        Args:
            namespace: 过滤命名空间
            tags: 过滤标签
            origin: 过滤来源
            format: 输出格式

        Returns:
            Agent 列表
        """
        namespace = kwargs.get("namespace")
        tags = kwargs.get("tags")
        origin_str = kwargs.get("origin")
        output_format = kwargs.get("format", "simple")

        try:
            directory = self._ensure_directory()

            # 解析 origin
            origin = None
            if origin_str:
                origin_map = {
                    "public": AgentOrigin.PUBLIC,
                    "namespace": AgentOrigin.NAMESPACE,
                    "bundled": AgentOrigin.BUNDLED,
                    "config": AgentOrigin.CONFIG,
                }
                origin = origin_map.get(origin_str)

            # 获取 Agent 列表
            agents = directory.list_agents(
                namespace=namespace,
                origin=origin,
                tags=tags,
            )

            # 格式化输出
            if output_format == "detailed":
                items = [self._format_agent_detailed(agent) for agent in agents]
            else:
                items = [self._format_agent_simple(agent) for agent in agents]

            self._log_operation("list_agents", {
                "namespace": namespace,
                "origin": origin_str,
                "tags": tags,
                "count": len(items),
            })

            return self._format_list(items, "agents")

        except Exception as e:
            logger.exception("Failed to list agents")
            return self._format_error(f"列出 Agent 失败: {str(e)}", "LIST_FAILED")

    def _format_agent_simple(self, agent: Any) -> dict[str, str]:
        """简单格式化 Agent 信息"""
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "description": agent.description[:100] if agent.description else "",
            "origin": agent.origin.value,
        }

    def _format_agent_detailed(self, agent: Any) -> dict[str, Any]:
        """详细格式化 Agent 信息"""
        result = {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "namespace": agent.namespace,
            "origin": agent.origin.value,
            "description": agent.description,
            "category": agent.category,
            "tags": agent.tags,
            "priority": agent.priority,
            "file_path": str(agent.file_path),
        }

        if agent.system_prompt_path:
            result["system_prompt_path"] = str(agent.system_prompt_path)

        # 添加元数据摘要
        if agent.metadata:
            model_config = agent.metadata.get("model", {})
            if model_config:
                result["model"] = model_config.get("model", "unknown")

            tools = agent.metadata.get("capabilities", {}).get("tools", [])
            if tools:
                result["tools_count"] = len(tools)

        return result
