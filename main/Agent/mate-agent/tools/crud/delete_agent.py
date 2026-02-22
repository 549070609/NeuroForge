"""
删除 Agent 工具

删除现有 Agent。
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


# 系统核心 Agent，禁止删除
PROTECTED_AGENTS = {
    "mate-agent",
    "builder-agent",
    "modifier-agent",
    "analyzer-agent",
    "tester-agent",
}


class DeleteAgentTool(MateAgentTool):
    """
    删除 Agent 工具

    删除现有 Agent，支持备份和依赖检查。

    参数:
        agent_id: Agent ID
        force: 强制删除 (忽略依赖检查和系统保护)
        backup: 删除前备份 (默认 True)
    """

    name = "delete_agent"
    description = "删除现有 Agent"
    category = "crud"
    requires_confirmation = True  # 需要用户确认
    risk_level = "high"
    timeout = 30

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "要删除的 Agent ID"
            },
            "force": {
                "type": "boolean",
                "description": "强制删除 (忽略依赖检查和系统保护)",
                "default": False
            },
            "backup": {
                "type": "boolean",
                "description": "删除前备份",
                "default": True
            }
        },
        "required": ["agent_id"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行删除 Agent

        Args:
            agent_id: Agent ID
            force: 强制删除
            backup: 是否备份

        Returns:
            删除结果
        """
        agent_id = kwargs.get("agent_id")
        force = kwargs.get("force", False)
        do_backup = kwargs.get("backup", True)

        if not agent_id:
            return self._format_error("agent_id 是必需参数", "MISSING_AGENT_ID")

        try:
            directory = self._ensure_directory()

            # 获取 Agent
            agent = directory.get_agent(agent_id)
            if not agent:
                return self._format_error(f"Agent '{agent_id}' 不存在", "AGENT_NOT_FOUND")

            # 检查是否为受保护的 Agent
            if agent_id in PROTECTED_AGENTS and not force:
                return self._format_error(
                    f"Agent '{agent_id}' 是系统核心 Agent，禁止删除。使用 force=True 强制删除。",
                    "PROTECTED_AGENT"
                )

            agent_dir = agent.file_path.parent

            # 检查依赖
            if not force:
                dependencies = self._check_dependencies(agent_id, directory)
                if dependencies:
                    return self._format_error(
                        f"Agent '{agent_id}' 被以下 Agent 依赖: {dependencies}。使用 force=True 强制删除。",
                        "HAS_DEPENDENCIES"
                    )

            # 备份
            backup_path = None
            if do_backup:
                backup_path = self._create_backup(agent_dir, agent_id)

            # 删除目录
            shutil.rmtree(agent_dir)

            # 刷新缓存
            directory.refresh()

            self._log_operation("delete_agent", {
                "agent_id": agent_id,
                "backup": str(backup_path) if backup_path else None,
                "force": force,
            })

            result_data = {
                "agent_id": agent_id,
                "deleted_path": str(agent_dir),
            }
            if backup_path:
                result_data["backup_path"] = str(backup_path)

            return self._format_success(
                f"成功删除 Agent '{agent_id}'",
                result_data
            )

        except Exception as e:
            logger.exception(f"Failed to delete agent: {agent_id}")
            return self._format_error(f"删除 Agent 失败: {str(e)}", "DELETE_FAILED")

    def _create_backup(self, agent_dir: Path, agent_id: str) -> Path:
        """
        创建 Agent 备份

        Args:
            agent_dir: Agent 目录
            agent_id: Agent ID

        Returns:
            备份路径
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_base = agent_dir.parent / ".backups"
        backup_base.mkdir(exist_ok=True)

        backup_path = backup_base / f"{agent_id}_{timestamp}_deleted"
        shutil.copytree(agent_dir, backup_path)

        return backup_path

    def _check_dependencies(self, agent_id: str, directory: Any) -> list[str]:
        """
        检查 Agent 依赖关系

        Args:
            agent_id: Agent ID
            directory: AgentDirectory 实例

        Returns:
            依赖此 Agent 的 Agent ID 列表
        """
        dependents = []

        for agent in directory.list_agents():
            if agent.agent_id == agent_id:
                continue

            # 检查 subagents 配置
            subagents = agent.metadata.get("subagents", {})
            for subagent_config in subagents.values():
                if isinstance(subagent_config, dict):
                    dep_agent = subagent_config.get("agent")
                    if dep_agent == agent_id:
                        dependents.append(agent.agent_id)

            # 检查工具依赖
            tools = agent.metadata.get("capabilities", {}).get("tools", [])
            if f"use_{agent_id}" in tools or agent_id in tools:
                dependents.append(agent.agent_id)

        return dependents
