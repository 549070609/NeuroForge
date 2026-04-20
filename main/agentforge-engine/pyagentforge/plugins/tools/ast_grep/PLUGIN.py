"""
AST-Grep 工具插件

提供 AST 语法树级别的代码搜索和替换能力
"""


from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginContext, PluginMetadata, PluginType
from pyagentforge.plugins.tools.ast_grep.binary_manager import BinaryManager
from pyagentforge.plugins.tools.ast_grep.tools import AstGrepReplaceTool, AstGrepSearchTool


class AstGrepPlugin(Plugin):
    """AST-Grep 工具插件"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="tool.ast-grep",
            name="AST-Grep Tools",
            version="1.0.0",
            type=PluginType.TOOL,
            description="AST-aware code search and replacement tools supporting 25 languages",
            author="PyAgentForge Team",
            dependencies=[],
            provides=["tools.ast_grep_search", "tools.ast_grep_replace"],
            priority=10,
        )

    def __init__(self):
        super().__init__()
        self._binary_manager: BinaryManager | None = None
        self._search_tool: AstGrepSearchTool | None = None
        self._replace_tool: AstGrepReplaceTool | None = None

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载时初始化"""
        await super().on_plugin_load(context)

        # 获取配置
        config = context.config.get("tool.ast-grep", {})
        auto_install = config.get("auto_install", False)

        # 初始化二进制管理器
        self._binary_manager = BinaryManager(
            logger=context.logger,
            auto_install=auto_install,
        )

        # 检查 ast-grep 可用性
        is_available = await self._binary_manager.check_availability()

        if is_available:
            version = await self._binary_manager.get_version()
            context.logger.info(
                f"AST-Grep plugin loaded, binary version: {version or 'unknown'}"
            )
        else:
            context.logger.warning(
                "AST-Grep binary not found. Tools will show install instructions. "
                "Set config 'tool.ast-grep.auto_install: true' to auto-install."
            )

    async def on_plugin_activate(self) -> None:
        """插件激活时创建工具"""
        await super().on_plugin_activate()

        if self._binary_manager and self.context:
            # 创建工具实例
            self._search_tool = AstGrepSearchTool(
                binary_manager=self._binary_manager,
                logger=self.context.logger,
            )
            self._replace_tool = AstGrepReplaceTool(
                binary_manager=self._binary_manager,
                logger=self.context.logger,
            )

            self.context.logger.info("AST-Grep tools activated")

    def get_tools(self) -> list[BaseTool]:
        """返回插件提供的工具"""
        tools = []
        if self._search_tool:
            tools.append(self._search_tool)
        if self._replace_tool:
            tools.append(self._replace_tool)
        return tools


# 插件导出
__all__ = ["AstGrepPlugin"]
