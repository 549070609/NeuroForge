"""
MateAgent 工具基类

扩展 pyagentforge.tools.base.BaseTool，添加:
- category: 工具分类
- requires_confirmation: 是否需要确认
- 延迟获取 AgentDirectory 和 TemplateLoader
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

# 直接定义基类，避免 pyagentforge 的导入问题
class PyAgentForgeBaseTool(ABC):
    """工具基类（内联版本）"""

    name: str = "base_tool"
    description: str = "基础工具"
    parameters_schema: dict[str, Any] = {}
    timeout: int = 60
    risk_level: str = "low"

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        pass

    def to_anthropic_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema,
        }

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

if TYPE_CHECKING:
    from main.Agent.core import AgentDirectory
    from .templates import TemplateLoader

logger = logging.getLogger(__name__)


class MateAgentTool(PyAgentForgeBaseTool):
    """
    MateAgent 工具基类

    扩展 pyagentforge 的 BaseTool，添加 Agent 构建相关功能。

    Attributes:
        category: 工具分类 (crud/config/analysis/system)
        requires_confirmation: 是否需要用户确认才能执行
    """

    category: str = "general"
    requires_confirmation: bool = False

    def __init__(
        self,
        agent_directory: "AgentDirectory | None" = None,
        template_loader: "TemplateLoader | None" = None,
    ):
        """
        初始化工具

        Args:
            agent_directory: Agent 目录实例 (可选，延迟获取)
            template_loader: 模板加载器实例 (可选，延迟获取)
        """
        self._directory = agent_directory
        self._template_loader = template_loader
        # 调用父类初始化（如果有的话）
        super().__init__()

    def _ensure_directory(self) -> "AgentDirectory":
        """
        确保 AgentDirectory 实例可用

        Returns:
            AgentDirectory 实例
        """
        if self._directory is None:
            from main.Agent.core import AgentDirectory
            self._directory = AgentDirectory()
            self._directory.scan()
        return self._directory

    def _ensure_template_loader(self) -> "TemplateLoader":
        """
        确保 TemplateLoader 实例可用

        Returns:
            TemplateLoader 实例
        """
        if self._template_loader is None:
            # 从 mate-agent/templates 目录导入
            import importlib.util
            from pathlib import Path

            templates_path = Path(__file__).parent.parent / "templates" / "__init__.py"
            spec = importlib.util.spec_from_file_location("mate_agent_templates", templates_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._template_loader = module.TemplateLoader()
        return self._template_loader

    def _log_operation(self, action: str, details: dict[str, Any]) -> None:
        """
        记录操作日志

        Args:
            action: 操作类型
            details: 操作详情
        """
        logger.info(f"[{self.name}] {action}: {details}")

    def _format_success(self, message: str, data: dict[str, Any] | None = None) -> str:
        """
        格式化成功消息

        Args:
            message: 成功消息
            data: 附加数据

        Returns:
            格式化的 JSON 字符串
        """
        import json
        result = {"success": True, "message": message}
        if data:
            result["data"] = data
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _format_error(self, message: str, error_code: str | None = None) -> str:
        """
        格式化错误消息

        Args:
            message: 错误消息
            error_code: 错误代码

        Returns:
            格式化的 JSON 字符串
        """
        import json
        result = {"success": False, "error": message}
        if error_code:
            result["error_code"] = error_code
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _format_list(self, items: list[Any], title: str = "Items") -> str:
        """
        格式化列表输出

        Args:
            items: 列表项
            title: 列表标题

        Returns:
            格式化的字符串
        """
        import json
        return json.dumps({
            "success": True,
            "count": len(items),
            title.lower(): items
        }, ensure_ascii=False, indent=2)
