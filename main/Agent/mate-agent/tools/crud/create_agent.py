"""
创建 Agent 工具

根据规格说明创建新的 Agent。
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class CreateAgentTool(MateAgentTool):
    """
    创建 Agent 工具

    根据规格说明创建新的 Agent，支持模板渲染。

    参数:
        agent_id: Agent 唯一标识符
        namespace: 命名空间 (默认 default)
        spec: Agent 规格说明
        template: 模板类型 (simple/tool/reasoning)
        system_prompt: 自定义提示词 (可选)
    """

    name = "create_agent"
    description = "根据规格说明创建新的 Agent"
    category = "crud"
    requires_confirmation = False
    timeout = 30

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "Agent 唯一标识符，使用 kebab-case 命名 (如: code-reviewer)"
            },
            "namespace": {
                "type": "string",
                "description": "命名空间，默认为 'default' (公共 Agent)",
                "default": "default"
            },
            "spec": {
                "type": "object",
                "description": "Agent 规格说明",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Agent 功能描述"
                    },
                    "model": {
                        "type": "object",
                        "description": "模型配置",
                        "properties": {
                            "provider": {"type": "string"},
                            "model": {"type": "string"},
                            "temperature": {"type": "number", "minimum": 0, "maximum": 1},
                            "max_tokens": {"type": "integer"}
                        }
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Agent 可用的工具列表"
                    },
                    "limits": {
                        "type": "object",
                        "description": "限制配置",
                        "properties": {
                            "max_iterations": {"type": "integer"},
                            "timeout": {"type": "integer"}
                        }
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签"
                    }
                },
                "required": ["description"]
            },
            "template": {
                "type": "string",
                "enum": ["simple", "tool", "reasoning"],
                "description": "模板类型",
                "default": "simple"
            },
            "system_prompt": {
                "type": "string",
                "description": "自定义系统提示词 (可选，不提供则使用模板默认)"
            }
        },
        "required": ["agent_id", "spec"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行创建 Agent

        Args:
            agent_id: Agent ID
            namespace: 命名空间
            spec: Agent 规格说明
            template: 模板类型
            system_prompt: 自定义提示词

        Returns:
            创建结果
        """
        agent_id = kwargs.get("agent_id")
        namespace = kwargs.get("namespace", "default")
        spec = kwargs.get("spec", {})
        template = kwargs.get("template", "simple")
        system_prompt = kwargs.get("system_prompt")

        # 验证必需参数
        if not agent_id:
            return self._format_error("agent_id 是必需参数", "MISSING_AGENT_ID")

        if not spec.get("description"):
            return self._format_error("spec.description 是必需参数", "MISSING_DESCRIPTION")

        # 验证 agent_id 格式
        if not self._validate_agent_id(agent_id):
            return self._format_error(
                f"agent_id 格式无效: {agent_id}，应使用 kebab-case (如: my-agent)",
                "INVALID_AGENT_ID"
            )

        try:
            # 获取目录
            directory = self._ensure_directory()

            # 检查是否已存在
            existing = directory.get_agent(agent_id)
            if existing:
                return self._format_error(
                    f"Agent '{agent_id}' 已存在: {existing.file_path}",
                    "AGENT_EXISTS"
                )

            # 确定目标目录
            target_dir = self._get_target_directory(agent_id, namespace)
            if target_dir.exists():
                return self._format_error(
                    f"目标目录已存在: {target_dir}",
                    "DIRECTORY_EXISTS"
                )

            # 获取模板加载器
            template_loader = self._ensure_template_loader()

            # 渲染配置和提示词
            config_content, prompt_content = template_loader.render(
                agent_id=agent_id,
                namespace=namespace,
                spec=spec,
                template_type=template,
            )

            # 如果提供了自定义提示词，使用自定义的
            if system_prompt:
                prompt_content = system_prompt

            # 创建目录和文件
            target_dir.mkdir(parents=True, exist_ok=True)

            # 写入 agent.yaml
            config_file = target_dir / "agent.yaml"
            config_file.write_text(config_content, encoding="utf-8")

            # 写入 system_prompt.md
            prompt_file = target_dir / "system_prompt.md"
            prompt_file.write_text(prompt_content, encoding="utf-8")

            # 刷新目录缓存
            directory.refresh()

            # 记录操作
            self._log_operation("create_agent", {
                "agent_id": agent_id,
                "namespace": namespace,
                "template": template,
                "path": str(target_dir),
            })

            return self._format_success(
                f"成功创建 Agent '{agent_id}'",
                {
                    "agent_id": agent_id,
                    "namespace": namespace,
                    "path": str(target_dir),
                    "config_file": str(config_file),
                    "prompt_file": str(prompt_file),
                }
            )

        except Exception as e:
            logger.exception(f"Failed to create agent: {agent_id}")
            return self._format_error(f"创建 Agent 失败: {str(e)}", "CREATE_FAILED")

    def _validate_agent_id(self, agent_id: str) -> bool:
        """
        验证 agent_id 格式

        规则:
        - 只包含小写字母、数字和连字符
        - 以字母开头
        - 长度 2-64
        """
        import re
        pattern = r"^[a-z][a-z0-9-]{1,63}$"
        return bool(re.match(pattern, agent_id))

    def _get_target_directory(self, agent_id: str, namespace: str) -> Path:
        """
        获取目标目录

        Args:
            agent_id: Agent ID
            namespace: 命名空间 (保留参数，但目前不使用)

        Returns:
            目标目录路径
        """
        from main.Agent.core import get_agent_base_config

        config = get_agent_base_config()
        base_path = config.get_full_path()

        # Agent 直接存储在根目录下
        return base_path / agent_id
