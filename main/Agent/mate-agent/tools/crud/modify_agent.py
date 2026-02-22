"""
修改 Agent 工具

修改现有 Agent 的配置。
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class ModifyAgentTool(MateAgentTool):
    """
    修改 Agent 工具

    修改现有 Agent 的配置，支持备份。

    参数:
        agent_id: Agent ID
        changes: 变更内容
        changelog: 变更说明
        backup: 是否备份 (默认 True)
    """

    name = "modify_agent"
    description = "修改现有 Agent 的配置"
    category = "crud"
    requires_confirmation = True  # 需要用户确认
    timeout = 30

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "要修改的 Agent ID"
            },
            "changes": {
                "type": "object",
                "description": "变更内容",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "更新描述"
                    },
                    "model": {
                        "type": "object",
                        "description": "更新模型配置",
                        "properties": {
                            "provider": {"type": "string"},
                            "model": {"type": "string"},
                            "temperature": {"type": "number"},
                            "max_tokens": {"type": "integer"}
                        }
                    },
                    "add_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "添加的工具"
                    },
                    "remove_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "移除的工具"
                    },
                    "limits": {
                        "type": "object",
                        "description": "更新限制配置"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "更新标签"
                    },
                    "add_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "添加标签"
                    },
                    "remove_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "移除标签"
                    }
                }
            },
            "changelog": {
                "type": "string",
                "description": "变更说明"
            },
            "backup": {
                "type": "boolean",
                "description": "是否在修改前备份",
                "default": True
            }
        },
        "required": ["agent_id", "changes"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行修改 Agent

        Args:
            agent_id: Agent ID
            changes: 变更内容
            changelog: 变更说明
            backup: 是否备份

        Returns:
            修改结果
        """
        agent_id = kwargs.get("agent_id")
        changes = kwargs.get("changes", {})
        changelog = kwargs.get("changelog", "")
        do_backup = kwargs.get("backup", True)

        if not agent_id:
            return self._format_error("agent_id 是必需参数", "MISSING_AGENT_ID")

        if not changes:
            return self._format_error("changes 不能为空", "EMPTY_CHANGES")

        try:
            directory = self._ensure_directory()

            # 获取 Agent
            agent = directory.get_agent(agent_id)
            if not agent:
                return self._format_error(f"Agent '{agent_id}' 不存在", "AGENT_NOT_FOUND")

            agent_dir = agent.file_path.parent

            # 备份
            backup_path = None
            if do_backup:
                backup_path = self._create_backup(agent_dir, agent_id)

            # 读取当前配置
            with open(agent.file_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            # 应用变更
            modified_fields = self._apply_changes(config, changes)

            if not modified_fields:
                return self._format_success("没有需要修改的字段")

            # 添加变更记录
            if "change_log" not in config:
                config["change_log"] = []

            config["change_log"].append({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": "modified",
                "changes": modified_fields,
                "description": changelog or "Configuration updated",
            })

            # 写回配置
            with open(agent.file_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            # 刷新缓存
            directory.refresh()

            self._log_operation("modify_agent", {
                "agent_id": agent_id,
                "changes": modified_fields,
                "backup": str(backup_path) if backup_path else None,
            })

            result_data = {
                "agent_id": agent_id,
                "modified_fields": modified_fields,
            }
            if backup_path:
                result_data["backup_path"] = str(backup_path)

            return self._format_success(
                f"成功修改 Agent '{agent_id}'",
                result_data
            )

        except Exception as e:
            logger.exception(f"Failed to modify agent: {agent_id}")
            return self._format_error(f"修改 Agent 失败: {str(e)}", "MODIFY_FAILED")

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

        backup_path = backup_base / f"{agent_id}_{timestamp}"
        shutil.copytree(agent_dir, backup_path)

        return backup_path

    def _apply_changes(self, config: dict[str, Any], changes: dict[str, Any]) -> list[str]:
        """
        应用变更到配置

        Args:
            config: 当前配置
            changes: 变更内容

        Returns:
            修改的字段列表
        """
        modified = []

        # 更新描述
        if "description" in changes:
            if "identity" not in config:
                config["identity"] = {}
            config["identity"]["description"] = changes["description"]
            modified.append("identity.description")

        # 更新模型
        if "model" in changes:
            if "model" not in config:
                config["model"] = {}
            config["model"].update(changes["model"])
            modified.append("model")

        # 更新限制
        if "limits" in changes:
            if "limits" not in config:
                config["limits"] = {}
            config["limits"].update(changes["limits"])
            modified.append("limits")

        # 更新标签
        if "tags" in changes:
            if "identity" not in config:
                config["identity"] = {}
            config["identity"]["tags"] = changes["tags"]
            modified.append("identity.tags")
        else:
            # 增量更新标签
            current_tags = set(config.get("identity", {}).get("tags", []))

            if "add_tags" in changes:
                current_tags.update(changes["add_tags"])
                modified.append("identity.tags (added)")

            if "remove_tags" in changes:
                current_tags.difference_update(changes["remove_tags"])
                modified.append("identity.tags (removed)")

            if "add_tags" in changes or "remove_tags" in changes:
                if "identity" not in config:
                    config["identity"] = {}
                config["identity"]["tags"] = list(current_tags)

        # 更新工具
        if "capabilities" not in config:
            config["capabilities"] = {}

        current_tools = set(config.get("capabilities", {}).get("tools", []))

        if "add_tools" in changes:
            current_tools.update(changes["add_tools"])
            modified.append("capabilities.tools (added)")

        if "remove_tools" in changes:
            current_tools.difference_update(changes["remove_tools"])
            modified.append("capabilities.tools (removed)")

        if "add_tools" in changes or "remove_tools" in changes:
            config["capabilities"]["tools"] = list(current_tools)

        return modified
