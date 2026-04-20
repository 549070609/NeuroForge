"""
Python AST Plugin

Provides AST-based code analysis tools for Python.
"""


from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginContext, PluginMetadata, PluginType
from pyagentforge.plugins.tools.python_ast.tools import (
    PythonASTAnalyzeComplexityTool,
    PythonASTExtractClassesTool,
    PythonASTFindCallsTool,
    PythonASTFindDefinitionsTool,
    PythonASTFindImportsTool,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class PythonASTPlugin(Plugin):
    """
    Python AST Plugin

    Provides AST-based code analysis tools:
    - python_find_definitions: Find functions, classes, methods
    - python_find_imports: Find import statements
    - python_find_calls: Find function calls
    - python_extract_classes: Extract class structures
    - python_analyze_complexity: Analyze code complexity
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="tool.python_ast",
            name="Python AST Tools",
            version="1.0.0",
            type=PluginType.TOOL,
            description="AST-based code analysis tools for Python",
            author="PyAgentForge Team",
            dependencies=[],
            provides=[
                "tools.python_find_definitions",
                "tools.python_find_imports",
                "tools.python_find_calls",
                "tools.python_extract_classes",
                "tools.python_analyze_complexity",
            ],
            priority=10,
        )

    def __init__(self):
        super().__init__()
        self._tools: list[BaseTool] = []

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载时初始化"""
        await super().on_plugin_load(context)
        context.logger.info("Python AST plugin loaded")

    async def on_plugin_activate(self) -> None:
        """插件激活时创建工具"""
        await super().on_plugin_activate()

        # Create tool instances
        self._tools = [
            PythonASTFindDefinitionsTool(),
            PythonASTFindImportsTool(),
            PythonASTFindCallsTool(),
            PythonASTExtractClassesTool(),
            PythonASTAnalyzeComplexityTool(),
        ]

        if self.context:
            self.context.logger.info(
                f"Python AST tools activated: {len(self._tools)} tools"
            )

    def get_tools(self) -> list[BaseTool]:
        """返回插件提供的工具"""
        return self._tools


# Plugin export
__all__ = ["PythonASTPlugin"]
