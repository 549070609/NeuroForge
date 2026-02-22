"""
模板加载器

加载和渲染 Agent 模板，支持:
- Jinja2 模板 (如果可用)
- 简单变量替换 (降级方案)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class TemplateLoader:
    """
    模板加载器

    加载和渲染 Agent 模板。

    支持两种渲染模式:
    1. Jinja2 模板 (如果安装了 jinja2)
    2. 简单变量替换 (降级方案)
    """

    def __init__(self, templates_dir: Path | None = None):
        """
        初始化模板加载器

        Args:
            templates_dir: 模板目录路径 (可选，默认使用内置模板目录)
        """
        if templates_dir:
            self._templates_dir = templates_dir
        else:
            self._templates_dir = Path(__file__).parent

        # 检查 Jinja2 是否可用
        self._jinja2_available = self._check_jinja2()

        # 模板缓存
        self._cache: dict[str, str] = {}

    def _check_jinja2(self) -> bool:
        """检查 Jinja2 是否可用"""
        try:
            import jinja2  # noqa: F401
            return True
        except ImportError:
            logger.debug("Jinja2 not available, using simple template replacement")
            return False

    def render(
        self,
        agent_id: str,
        namespace: str,
        spec: dict[str, Any],
        template_type: str = "simple",
    ) -> tuple[str, str]:
        """
        渲染 Agent 模板

        Args:
            agent_id: Agent ID
            namespace: 命名空间
            spec: Agent 规格说明
            template_type: 模板类型 (simple/tool/reasoning)

        Returns:
            (config_content, prompt_content) 元组
        """
        # 构建模板上下文
        context = self._build_context(agent_id, namespace, spec)

        # 渲染配置文件
        config_content = self._render_config(context, template_type)

        # 渲染提示词文件
        prompt_content = self._render_prompt(context, template_type)

        return config_content, prompt_content

    def _build_context(
        self,
        agent_id: str,
        namespace: str,
        spec: dict[str, Any],
    ) -> dict[str, Any]:
        """
        构建模板上下文

        Args:
            agent_id: Agent ID
            namespace: 命名空间
            spec: Agent 规格说明

        Returns:
            模板上下文字典
        """
        # 默认模型配置
        default_model = {
            "provider": "anthropic",
            "model": "claude-haiku-4-5-20251001",
            "temperature": 0.7,
            "max_tokens": 4096,
        }

        # 合并用户提供的模型配置
        model_config = {**default_model, **spec.get("model", {})}

        # 默认限制
        default_limits = {
            "max_iterations": 10,
            "timeout": 300,
        }
        limits = {**default_limits, **spec.get("limits", {})}

        return {
            "agent_id": agent_id,
            "namespace": namespace,
            "name": spec.get("name", agent_id),
            "description": spec.get("description", ""),
            "model": model_config,
            "limits": limits,
            "tools": spec.get("tools", []),
            "tags": spec.get("tags", []),
            "category": spec.get("category", "general"),
        }

    def _render_config(self, context: dict[str, Any], template_type: str) -> str:
        """
        渲染配置文件

        Args:
            context: 模板上下文
            template_type: 模板类型

        Returns:
            YAML 配置内容
        """
        # 直接生成 YAML 配置
        config = self._generate_config_dict(context, template_type)
        return yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def _generate_config_dict(self, context: dict[str, Any], template_type: str) -> dict[str, Any]:
        """
        生成配置字典

        Args:
            context: 模板上下文
            template_type: 模板类型

        Returns:
            配置字典
        """
        config = {
            "identity": {
                "name": context["name"],
                "description": context["description"],
                "tags": context["tags"],
            },
            "category": context["category"],
            "model": context["model"],
            "limits": context["limits"],
        }

        # 根据模板类型添加特定配置
        if context["tools"]:
            config["capabilities"] = {
                "tools": context["tools"],
            }

        if template_type == "reasoning":
            # 推理型 Agent 特定配置
            config["model"]["temperature"] = 0.3
            config["model"]["max_tokens"] = 8192
            config["capabilities"] = config.get("capabilities", {})
            config["capabilities"]["thinking"] = True

        elif template_type == "tool":
            # 工具型 Agent 特定配置
            config["model"]["temperature"] = 0.5
            config["limits"]["max_iterations"] = 20

        return config

    def _render_prompt(self, context: dict[str, Any], template_type: str) -> str:
        """
        渲染提示词文件

        Args:
            context: 模板上下文
            template_type: 模板类型

        Returns:
            Markdown 提示词内容
        """
        template_name = f"{template_type}-agent"

        # 尝试加载模板文件
        template_path = self._templates_dir / template_name / "system_prompt.md.tmpl"

        if template_path.exists():
            template_content = template_path.read_text(encoding="utf-8")
            return self._render_template(template_content, context)
        else:
            # 使用内置默认模板
            return self._render_default_prompt(context, template_type)

    def _render_template(self, template_content: str, context: dict[str, Any]) -> str:
        """
        渲染模板内容

        Args:
            template_content: 模板内容
            context: 模板上下文

        Returns:
            渲染后的内容
        """
        if self._jinja2_available:
            return self._render_jinja2(template_content, context)
        else:
            return self._render_simple(template_content, context)

    def _render_jinja2(self, template_content: str, context: dict[str, Any]) -> str:
        """使用 Jinja2 渲染"""
        from jinja2 import Template
        template = Template(template_content)
        return template.render(**context)

    def _render_simple(self, template_content: str, context: dict[str, Any]) -> str:
        """简单变量替换"""
        result = template_content

        # 替换 {{ variable }} 格式
        import re

        def replace_var(match):
            var_name = match.group(1).strip()
            # 支持嵌套访问 (如 model.temperature)
            parts = var_name.split(".")
            value = context
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, "")
                else:
                    value = ""
                    break

            if isinstance(value, (list, dict)):
                import json
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        result = re.sub(r"\{\{\s*(\w+(?:\.\w+)*)\s*\}\}", replace_var, result)
        return result

    def _render_default_prompt(self, context: dict[str, Any], template_type: str) -> str:
        """
        生成默认提示词

        Args:
            context: 模板上下文
            template_type: 模板类型

        Returns:
            默认提示词内容
        """
        name = context["name"]
        description = context["description"]
        tools = context["tools"]

        lines = [
            f"# {name}",
            "",
            f"{description}",
            "",
        ]

        if template_type == "reasoning":
            lines.extend([
                "## 思考模式",
                "",
                "你是一个推理型 Agent，专注于复杂问题的分析和推理。",
                "在执行任务时，请：",
                "1. 仔细分析问题，理解上下文",
                "2. 制定执行计划",
                "3. 逐步执行并验证结果",
                "4. 反思和优化方案",
                "",
            ])
        elif template_type == "tool":
            lines.extend([
                "## 工具使用",
                "",
                "你是一个工具型 Agent，擅长使用各种工具完成任务。",
                "请充分利用可用工具，高效完成用户请求。",
                "",
            ])

        if tools:
            lines.extend([
                "## 可用工具",
                "",
                "你可以使用以下工具：",
            ])
            for tool in tools:
                lines.append(f"- `{tool}`")
            lines.append("")

        lines.extend([
            "## 注意事项",
            "",
            "- 保持专业和高效",
            "- 遇到不确定的情况主动询问",
            "- 完成任务后提供清晰的总结",
            "",
        ])

        return "\n".join(lines)

    def list_templates(self) -> list[str]:
        """
        列出可用模板

        Returns:
            模板名称列表
        """
        templates = []

        for item in self._templates_dir.iterdir():
            if item.is_dir() and item.name.endswith("-agent"):
                templates.append(item.name.replace("-agent", ""))

        # 始终包含内置模板
        for t in ["simple", "tool", "reasoning"]:
            if t not in templates:
                templates.append(t)

        return sorted(templates)
