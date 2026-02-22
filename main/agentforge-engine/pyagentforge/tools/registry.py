"""
工具注册表

管理所有工具的注册、发现和查询
"""

import importlib
from pathlib import Path
from typing import Any, Callable, Iterator

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册表"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._tool_factories: dict[str, Callable[[], BaseTool]] = {}

    def register(self, tool: BaseTool) -> None:
        """
        注册工具

        Args:
            tool: 工具实例
        """
        if tool.name in self._tools:
            logger.warning(
                "Tool already registered, overwriting",
                extra_data={"tool_name": tool.name},
            )
        self._tools[tool.name] = tool
        logger.debug(
            "Registered tool",
            extra_data={"tool_name": tool.name},
        )

    def unregister(self, name: str) -> bool:
        """
        注销工具

        Args:
            name: 工具名称

        Returns:
            是否成功注销
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> BaseTool | None:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            工具实例或 None
        """
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools

    def get_all(self) -> dict[str, BaseTool]:
        """获取所有工具"""
        return self._tools.copy()

    def get_schemas(self) -> list[dict[str, Any]]:
        """获取所有工具的 Schema"""
        return [tool.to_anthropic_schema() for tool in self._tools.values()]

    def filter_by_permission(
        self,
        allowed: list[str],
    ) -> "ToolRegistry":
        """
        按权限过滤工具

        Args:
            allowed: 允许的工具名称列表，包含 "*" 表示所有

        Returns:
            新的过滤后的工具注册表
        """
        new_registry = ToolRegistry()

        if "*" in allowed:
            # 允许所有工具
            for name, tool in self._tools.items():
                new_registry.register(tool)
        else:
            # 只允许指定工具
            for name in allowed:
                if name in self._tools:
                    new_registry.register(self._tools[name])

        return new_registry

    def register_builtin_tools(self) -> None:
        """注册内置工具 (核心 6 个)"""
        from pyagentforge.tools.builtin.bash import BashTool
        from pyagentforge.tools.builtin.read import ReadTool
        from pyagentforge.tools.builtin.write import WriteTool
        from pyagentforge.tools.builtin.edit import EditTool
        from pyagentforge.tools.builtin.glob import GlobTool
        from pyagentforge.tools.builtin.grep import GrepTool

        builtin_tools = [
            BashTool(),
            ReadTool(),
            WriteTool(),
            EditTool(),
            GlobTool(),
            GrepTool(),
        ]

        for tool in builtin_tools:
            self.register(tool)

        logger.info(
            "Registered builtin tools",
            extra_data={"count": len(builtin_tools)},
        )

    def register_p0_tools(self) -> None:
        """注册 P0 高优先级工具"""
        from pyagentforge.tools.builtin.ls import LsTool
        from pyagentforge.tools.builtin.lsp import LSPTool
        from pyagentforge.tools.builtin.question import QuestionTool, ConfirmTool

        p0_tools = [
            LsTool(),
            LSPTool(),
            QuestionTool(),
            ConfirmTool(),
        ]

        for tool in p0_tools:
            self.register(tool)

        logger.info(
            "Registered P0 tools",
            extra_data={"count": len(p0_tools)},
        )

    def register_p1_tools(
        self,
        working_dir: str | None = None,
        permission_checker: "PermissionChecker | None" = None,
    ) -> None:
        """注册 P1 中优先级工具"""
        from pyagentforge.codesearch import create_codesearch_tool, CodeSearchConfig
        from pyagentforge.tools.builtin.apply_patch import ApplyPatchTool, DiffTool
        from pyagentforge.tools.builtin.plan import PlanTool

        # 创建增强版 CodeSearch 工具
        codesearch_config = CodeSearchConfig()
        codesearch_tool = create_codesearch_tool(
            config=codesearch_config,
            permission_checker=permission_checker,
            workspace_root=working_dir,
        )

        p1_tools = [
            codesearch_tool,
            ApplyPatchTool(),
            DiffTool(),
            PlanTool(),
        ]

        for tool in p1_tools:
            self.register(tool)

        logger.info(
            "Registered P1 tools (with enhanced CodeSearch)",
            extra_data={"count": len(p1_tools)},
        )

    def register_p2_tools(self) -> None:
        """注册 P2 低优先级工具"""
        from pyagentforge.tools.builtin.truncation import TruncationTool, ContextCompactTool
        from pyagentforge.tools.builtin.invalid import InvalidTool, ToolSuggestionTool
        from pyagentforge.tools.builtin.external_directory import ExternalDirectoryTool, WorkspaceTool

        p2_tools = [
            TruncationTool(),
            ContextCompactTool(),
            InvalidTool(available_tools=list(self._tools.keys())),
            ToolSuggestionTool(),
            ExternalDirectoryTool(),
            WorkspaceTool(),
        ]

        for tool in p2_tools:
            self.register(tool)

        # 更新 InvalidTool 的可用工具列表
        if self.has("invalid"):
            self._tools["invalid"].available_tools = list(self._tools.keys())

        logger.info(
            "Registered P2 tools",
            extra_data={"count": len(p2_tools)},
        )

    def register_extended_tools(self) -> None:
        """注册扩展工具 (web, todo 等)"""
        from pyagentforge.tools.builtin.webfetch import WebFetchTool
        from pyagentforge.tools.builtin.websearch import WebSearchTool
        from pyagentforge.tools.builtin.todo import TodoWriteTool, TodoReadTool
        from pyagentforge.tools.builtin.multiedit import MultiEditTool

        extended_tools = [
            WebFetchTool(),
            WebSearchTool(),
            MultiEditTool(),
        ]

        for tool in extended_tools:
            self.register(tool)

        # Todo 工具需要特殊处理
        todo_write = TodoWriteTool()
        todo_read = TodoReadTool(todo_write)
        self.register(todo_write)
        self.register(todo_read)

        logger.info(
            "Registered extended tools",
            extra_data={"count": len(extended_tools) + 2},
        )

    def register_task_tool(
        self,
        provider: Any,
        current_depth: int = 0,
        ask_callback: Callable | None = None,
    ) -> None:
        """
        注册 Task 工具

        Args:
            provider: LLM Provider 实例
            current_depth: 当前子代理深度
            ask_callback: 用户确认回调
        """
        from pyagentforge.tools.builtin.task import TaskTool

        task_tool = TaskTool(
            provider=provider,
            tool_registry=self,
            current_depth=current_depth,
            ask_callback=ask_callback,
        )
        self.register(task_tool)

        logger.info(
            "Registered Task tool",
            extra_data={"depth": current_depth},
        )

    def register_factory(self, name: str, factory: Callable[[], BaseTool]) -> None:
        """
        注册工具工厂

        工厂函数在需要时才创建工具实例

        Args:
            name: 工具名称
            factory: 创建工具的工厂函数
        """
        self._tool_factories[name] = factory
        logger.debug(
            "Registered tool factory",
            extra_data={"tool_name": name},
        )

    def get_or_create(self, name: str) -> BaseTool | None:
        """
        获取工具，如果不存在则尝试通过工厂创建

        Args:
            name: 工具名称

        Returns:
            工具实例或 None
        """
        # 先检查已注册的工具
        if name in self._tools:
            return self._tools[name]

        # 尝试通过工厂创建
        if name in self._tool_factories:
            tool = self._tool_factories[name]()
            self.register(tool)
            return tool

        return None

    def auto_discover_tools(self, package_path: str = "pyagentforge.tools.builtin") -> int:
        """
        自动发现并注册工具

        扫描指定包下的所有模块，自动发现 BaseTool 子类

        Args:
            package_path: 要扫描的包路径

        Returns:
            发现的工具数量
        """
        discovered = 0

        try:
            # 导入包
            package = importlib.import_module(package_path)
            package_dir = Path(package.__file__).parent

            # 扫描所有 Python 文件
            for py_file in package_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue

                module_name = py_file.stem
                full_module = f"{package_path}.{module_name}"

                try:
                    module = importlib.import_module(full_module)

                    # 查找所有 BaseTool 子类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)

                        # 检查是否是 BaseTool 子类（但不是 BaseTool 本身）
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseTool)
                            and attr is not BaseTool
                            and not attr.__name__.startswith("_")
                        ):
                            try:
                                # 尝试实例化（无参构造）
                                tool_instance = attr()

                                # 检查是否已注册
                                if tool_instance.name not in self._tools:
                                    self.register(tool_instance)
                                    discovered += 1

                            except TypeError:
                                # 需要参数的工具，跳过
                                logger.debug(
                                    "Skipping tool requiring arguments",
                                    extra_data={"tool": attr_name},
                                )
                            except Exception as e:
                                logger.warning(
                                    "Failed to instantiate tool",
                                    extra_data={"tool": attr_name, "error": str(e)},
                                )

                except ImportError as e:
                    logger.debug(
                        "Failed to import module",
                        extra_data={"module": full_module, "error": str(e)},
                    )

        except Exception as e:
            logger.error(
                "Auto-discovery failed",
                extra_data={"error": str(e)},
            )

        logger.info(
            "Auto-discovered tools",
            extra_data={"count": discovered},
        )

        return discovered

    def register_all_tools(self) -> None:
        """注册所有工具"""
        self.register_builtin_tools()
        self.register_p0_tools()
        self.register_p1_tools()
        self.register_p2_tools()
        self.register_extended_tools()

        logger.info(
            "Registered all tools",
            extra_data={"total": len(self._tools)},
        )

    def register_command_tools(self) -> None:
        """注册命令工具"""
        from pyagentforge.commands.tool import CommandTool, ListCommandsTool
        from pyagentforge.commands.registry import get_command_registry

        registry = get_command_registry()
        command_tool = CommandTool(registry=registry)
        list_commands_tool = ListCommandsTool(registry=registry)

        self.register(command_tool)
        self.register(list_commands_tool)

        logger.info(
            "Registered command tools",
            extra_data={"count": 2},
        )

    def __iter__(self) -> Iterator[BaseTool]:
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={list(self._tools.keys())})"
