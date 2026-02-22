"""
渲染模板工具

渲染 Agent 模板并返回结果。
"""

from __future__ import annotations

import logging
from typing import Any

from ..base import MateAgentTool

logger = logging.getLogger(__name__)


class RenderTemplateTool(MateAgentTool):
    """
    渲染模板工具

    渲染 Agent 模板，返回配置和提示词内容而不写入文件。
    用于预览和验证模板结果。

    参数:
        agent_id: Agent ID
        namespace: 命名空间
        spec: Agent 规格说明
        template: 模板类型
    """

    name = "render_template"
    description = "渲染 Agent 模板，返回配置和提示词预览"
    category = "config"
    requires_confirmation = False
    timeout = 10

    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "agent_id": {
                "type": "string",
                "description": "Agent ID"
            },
            "namespace": {
                "type": "string",
                "description": "命名空间",
                "default": "default"
            },
            "spec": {
                "type": "object",
                "description": "Agent 规格说明",
                "properties": {
                    "description": {"type": "string"},
                    "model": {"type": "object"},
                    "tools": {"type": "array", "items": {"type": "string"}},
                    "limits": {"type": "object"},
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["description"]
            },
            "template": {
                "type": "string",
                "enum": ["simple", "tool", "reasoning"],
                "description": "模板类型",
                "default": "simple"
            }
        },
        "required": ["agent_id", "spec"]
    }

    async def execute(self, **kwargs: Any) -> str:
        """
        执行模板渲染

        Args:
            agent_id: Agent ID
            namespace: 命名空间
            spec: Agent 规格说明
            template: 模板类型

        Returns:
            渲染结果 (config_content, prompt_content)
        """
        agent_id = kwargs.get("agent_id")
        namespace = kwargs.get("namespace", "default")
        spec = kwargs.get("spec", {})
        template_type = kwargs.get("template", "simple")

        if not agent_id:
            return self._format_error("agent_id 是必需参数", "MISSING_AGENT_ID")

        if not spec.get("description"):
            return self._format_error("spec.description 是必需参数", "MISSING_DESCRIPTION")

        try:
            # 获取模板加载器
            template_loader = self._ensure_template_loader()

            # 渲染模板
            config_content, prompt_content = template_loader.render(
                agent_id=agent_id,
                namespace=namespace,
                spec=spec,
                template_type=template_type,
            )

            self._log_operation("render_template", {
                "agent_id": agent_id,
                "template": template_type,
            })

            return self._format_success("模板渲染完成", {
                "agent_id": agent_id,
                "namespace": namespace,
                "template": template_type,
                "config_content": config_content,
                "prompt_content": prompt_content,
            })

        except Exception as e:
            logger.exception(f"Failed to render template for: {agent_id}")
            return self._format_error(f"模板渲染失败: {str(e)}", "RENDER_FAILED")
