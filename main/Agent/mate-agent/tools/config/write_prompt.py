"""
写入提示词工具

写入或更新 Agent 的系统提示词。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class WritePromptTool(MateAgentTool):
    """
    写入提示词工具

    写入或更新 Agent 的系统提示词。

    参数:
        agent_id: Agent ID
        content: 提示词内容
        mode: 写入模式 (overwrite/append/prepend)
        backup: 是否备份 (默认 True)
    """

    name = "write_prompt"
    description = "写入或更新 Agent 的系统提示词"
    category = "config"
    requires_confirmation = True  # 需要用户确认
    timeout = 20

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "Agent ID"
            },
            "content": {
                "type": "string",
                "description": "提示词内容"
            },
            "mode": {
                "type": "string",
                "enum": ["overwrite", "append", "prepend"],
                "description": "写入模式",
                "default": "overwrite"
            },
            "backup": {
                "type": "boolean",
                "description": "是否备份",
                "default": True
            }
        },
        "required": ["agent_id", "content"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行写入提示词

        Args:
            agent_id: Agent ID
            content: 提示词内容
            mode: 写入模式
            backup: 是否备份

        Returns:
            写入结果
        """
        agent_id = kwargs.get("agent_id")
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "overwrite")
        do_backup = kwargs.get("backup", True)

        if not agent_id:
            return self._format_error("agent_id 是必需参数", "MISSING_AGENT_ID")

        if not content:
            return self._format_error("content 不能为空", "EMPTY_CONTENT")

        try:
            directory = self._ensure_directory()

            # 获取 Agent
            agent = directory.get_agent(agent_id)
            if not agent:
                return self._format_error(f"Agent '{agent_id}' 不存在", "AGENT_NOT_FOUND")

            # 确定提示词文件路径
            prompt_path = agent.file_path.parent / "system_prompt.md"

            # 读取现有内容
            existing_content = ""
            if prompt_path.exists():
                existing_content = prompt_path.read_text(encoding="utf-8")

            # 备份
            backup_path = None
            if do_backup and existing_content:
                backup_path = self._create_backup(prompt_path, agent_id)

            # 计算新内容
            if mode == "overwrite":
                new_content = content
            elif mode == "append":
                new_content = existing_content + "\n\n" + content
            elif mode == "prepend":
                new_content = content + "\n\n" + existing_content
            else:
                new_content = content

            # 写入
            prompt_path.write_text(new_content.strip() + "\n", encoding="utf-8")

            # 更新时间戳 (在配置中记录)
            self._update_config_timestamp(agent.file_path)

            self._log_operation("write_prompt", {
                "agent_id": agent_id,
                "mode": mode,
                "content_length": len(content),
                "backup": str(backup_path) if backup_path else None,
            })

            result_data = {
                "agent_id": agent_id,
                "prompt_path": str(prompt_path),
                "mode": mode,
                "total_length": len(new_content),
            }
            if backup_path:
                result_data["backup_path"] = str(backup_path)

            return self._format_success(
                f"成功写入提示词",
                result_data
            )

        except Exception as e:
            logger.exception(f"Failed to write prompt for: {agent_id}")
            return self._format_error(f"写入提示词失败: {str(e)}", "WRITE_FAILED")

    def _create_backup(self, prompt_path: Path, agent_id: str) -> Path:
        """
        创建提示词备份

        Args:
            prompt_path: 提示词文件路径
            agent_id: Agent ID

        Returns:
            备份路径
        """
        import shutil

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_base = prompt_path.parent / ".backups"
        backup_base.mkdir(exist_ok=True)

        backup_path = backup_base / f"{agent_id}_prompt_{timestamp}.md"
        shutil.copy2(prompt_path, backup_path)

        return backup_path

    def _update_config_timestamp(self, config_path: Path) -> None:
        """
        更新配置文件中的时间戳

        Args:
            config_path: 配置文件路径
        """
        import yaml

        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            # 更新 prompt_updated 字段
            if "metadata" not in config:
                config["metadata"] = {}

            config["metadata"]["prompt_updated"] = datetime.utcnow().isoformat() + "Z"

            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        except Exception:
            # 忽略时间戳更新失败
            pass
