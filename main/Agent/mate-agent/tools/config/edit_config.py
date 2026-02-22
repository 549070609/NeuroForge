"""
编辑配置工具

直接编辑 Agent 配置文件。
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class EditConfigTool(MateAgentTool):
    """
    编辑配置工具

    直接编辑 Agent 的配置文件，支持:
    - 设置字段值
    - 删除字段
    - 合并配置

    参数:
        agent_id: Agent ID
        operation: 操作类型 (set/delete/merge)
        path: 配置路径 (如: model.temperature)
        value: 值 (用于 set 和 merge)
    """

    name = "edit_config"
    description = "直接编辑 Agent 配置文件"
    category = "config"
    requires_confirmation = True  # 需要用户确认
    timeout = 20

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "要编辑的 Agent ID"
            },
            "operation": {
                "type": "string",
                "enum": ["set", "delete", "merge"],
                "description": "操作类型"
            },
            "path": {
                "type": "string",
                "description": "配置路径 (如: model.temperature)"
            },
            "value": {
                "description": "要设置的值 (用于 set 和 merge 操作)"
            }
        },
        "required": ["agent_id", "operation", "path"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行配置编辑

        Args:
            agent_id: Agent ID
            operation: 操作类型
            path: 配置路径
            value: 值

        Returns:
            编辑结果
        """
        agent_id = kwargs.get("agent_id")
        operation = kwargs.get("operation")
        path = kwargs.get("path")
        value = kwargs.get("value")

        if not agent_id:
            return self._format_error("agent_id 是必需参数", "MISSING_AGENT_ID")

        if not operation:
            return self._format_error("operation 是必需参数", "MISSING_OPERATION")

        if not path:
            return self._format_error("path 是必需参数", "MISSING_PATH")

        if operation in ("set", "merge") and value is None:
            return self._format_error(f"operation '{operation}' 需要提供 value", "MISSING_VALUE")

        try:
            directory = self._ensure_directory()

            # 获取 Agent
            agent = directory.get_agent(agent_id)
            if not agent:
                return self._format_error(f"Agent '{agent_id}' 不存在", "AGENT_NOT_FOUND")

            # 读取配置
            with open(agent.file_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            # 记录旧值
            old_value = self._get_value_by_path(config, path)

            # 执行操作
            if operation == "set":
                self._set_value_by_path(config, path, value)
            elif operation == "delete":
                self._delete_value_by_path(config, path)
            elif operation == "merge":
                current = self._get_value_by_path(config, path)
                if isinstance(current, dict) and isinstance(value, dict):
                    current.update(value)
                else:
                    return self._format_error(
                        f"merge 操作要求路径 '{path}' 和 value 都是字典类型",
                        "MERGE_TYPE_ERROR"
                    )

            # 写回配置
            with open(agent.file_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            # 刷新缓存
            directory.refresh()

            self._log_operation("edit_config", {
                "agent_id": agent_id,
                "operation": operation,
                "path": path,
                "old_value": str(old_value)[:100],
            })

            return self._format_success(
                f"成功编辑配置",
                {
                    "agent_id": agent_id,
                    "operation": operation,
                    "path": path,
                    "old_value": old_value,
                    "new_value": self._get_value_by_path(config, path),
                }
            )

        except Exception as e:
            logger.exception(f"Failed to edit config for: {agent_id}")
            return self._format_error(f"配置编辑失败: {str(e)}", "EDIT_FAILED")

    def _get_value_by_path(self, config: dict[str, Any], path: str) -> Any:
        """
        通过路径获取值

        Args:
            config: 配置字典
            path: 路径 (如: model.temperature)

        Returns:
            路径对应的值
        """
        parts = path.split(".")
        value = config

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value

    def _set_value_by_path(self, config: dict[str, Any], path: str, value: Any) -> None:
        """
        通过路径设置值

        Args:
            config: 配置字典
            path: 路径
            value: 值
        """
        parts = path.split(".")
        current = config

        # 遍历到倒数第二层
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # 设置最后一层的值
        current[parts[-1]] = value

    def _delete_value_by_path(self, config: dict[str, Any], path: str) -> bool:
        """
        通过路径删除值

        Args:
            config: 配置字典
            path: 路径

        Returns:
            是否成功删除
        """
        parts = path.split(".")
        current = config

        # 遍历到倒数第二层
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                return False
            current = current[part]

        # 删除最后一层的键
        if parts[-1] in current:
            del current[parts[-1]]
            return True

        return False
