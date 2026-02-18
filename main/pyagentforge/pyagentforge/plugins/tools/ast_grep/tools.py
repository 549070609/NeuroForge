"""
AST-Grep 工具实现

提供 ast_grep_search 和 ast_grep_replace 两个工具
"""

import logging
from typing import Any, List, Optional

from pyagentforge.kernel.base_tool import BaseTool

from pyagentforge.plugins.tools.ast_grep.binary_manager import BinaryManager
from pyagentforge.plugins.tools.ast_grep.cli import run_sg
from pyagentforge.plugins.tools.ast_grep.constants import CLI_LANGUAGES, DEFAULT_TIMEOUT_MS, DEFAULT_MAX_MATCHES
from pyagentforge.plugins.tools.ast_grep.result_formatter import format_search_result, format_replace_result, get_empty_result_hint


class AstGrepSearchTool(BaseTool):
    """AST 语法树搜索工具"""

    name = "ast_grep_search"
    description = (
        "使用 AST 语法树搜索代码模式。支持 25 种语言。"
        "使用元变量: $VAR (单个节点), $$$ (多个节点)。"
        "模式必须是完整的 AST 节点。"
        "例如: 'console.log($MSG)', 'def $FUNC($$$):', 'async function $NAME($$$) { $$$ }'"
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "AST 模式，使用 $VAR 匹配单个节点，$$$ 匹配多个节点",
            },
            "lang": {
                "type": "string",
                "enum": list(CLI_LANGUAGES),
                "description": "目标语言",
            },
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "搜索路径，默认为当前目录",
            },
            "globs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "文件过滤模式，! 前缀表示排除",
            },
            "context": {
                "type": "integer",
                "description": "匹配周围的上下文行数",
            },
        },
        "required": ["pattern", "lang"],
    }
    timeout = DEFAULT_TIMEOUT_MS // 1000  # 转换为秒
    risk_level = "low"

    def __init__(
        self,
        binary_manager: BinaryManager,
        logger: Optional[logging.Logger] = None,
    ):
        """
        初始化搜索工具

        Args:
            binary_manager: 二进制管理器
            logger: 日志记录器
        """
        self.binary_manager = binary_manager
        self.logger = logger or logging.getLogger(__name__)

    async def execute(self, **kwargs) -> str:
        """
        执行 AST 搜索

        Args:
            pattern: AST 模式
            lang: 目标语言
            paths: 搜索路径
            globs: 文件过滤
            context: 上下文行数

        Returns:
            str: 搜索结果
        """
        pattern = kwargs.get("pattern", "")
        lang = kwargs.get("lang", "")
        paths = kwargs.get("paths")
        globs = kwargs.get("globs")
        context = kwargs.get("context", 0)

        # 检查可用性
        if not await self.binary_manager.is_available():
            return self.binary_manager.get_install_hint()

        # 获取二进制路径
        binary_path = self.binary_manager.get_binary_path()
        if not binary_path:
            return self.binary_manager.get_install_hint()

        # 执行搜索
        result = await run_sg(
            pattern=pattern,
            lang=lang,
            binary_path=binary_path,
            paths=paths,
            globs=globs,
            context=context,
            logger=self.logger,
        )

        # 格式化结果
        output = format_search_result(result)

        # 如果无结果，提供提示
        if result.total_matches == 0 and not result.error:
            hint = get_empty_result_hint(pattern, lang)
            if hint:
                output += f"\n\n{hint}"

        return output


class AstGrepReplaceTool(BaseTool):
    """AST 语法树替换工具"""

    name = "ast_grep_replace"
    description = (
        "使用 AST 语法树安全替换代码。"
        "默认为预览模式 (dry-run=True)。"
        "在 rewrite 中使用 $VAR 保留匹配内容。"
        "例如: pattern='console.log($MSG)' rewrite='logger.info($MSG)'"
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "要匹配的 AST 模式",
            },
            "rewrite": {
                "type": "string",
                "description": "替换模式，可使用 $VAR 引用匹配内容",
            },
            "lang": {
                "type": "string",
                "enum": list(CLI_LANGUAGES),
                "description": "目标语言",
            },
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "搜索路径",
            },
            "globs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "文件过滤模式",
            },
            "dry_run": {
                "type": "boolean",
                "default": True,
                "description": "预览模式，不实际修改文件",
            },
        },
        "required": ["pattern", "rewrite", "lang"],
    }
    timeout = DEFAULT_TIMEOUT_MS // 1000  # 转换为秒
    risk_level = "medium"  # 替换操作风险较高

    def __init__(
        self,
        binary_manager: BinaryManager,
        logger: Optional[logging.Logger] = None,
    ):
        """
        初始化替换工具

        Args:
            binary_manager: 二进制管理器
            logger: 日志记录器
        """
        self.binary_manager = binary_manager
        self.logger = logger or logging.getLogger(__name__)

    async def execute(self, **kwargs) -> str:
        """
        执行 AST 替换

        Args:
            pattern: 要匹配的 AST 模式
            rewrite: 替换模式
            lang: 目标语言
            paths: 搜索路径
            globs: 文件过滤
            dry_run: 是否预览模式

        Returns:
            str: 替换结果
        """
        pattern = kwargs.get("pattern", "")
        rewrite = kwargs.get("rewrite", "")
        lang = kwargs.get("lang", "")
        paths = kwargs.get("paths")
        globs = kwargs.get("globs")
        dry_run = kwargs.get("dry_run", True)

        # 检查可用性
        if not await self.binary_manager.is_available():
            return self.binary_manager.get_install_hint()

        # 获取二进制路径
        binary_path = self.binary_manager.get_binary_path()
        if not binary_path:
            return self.binary_manager.get_install_hint()

        # 执行替换
        result = await run_sg(
            pattern=pattern,
            lang=lang,
            binary_path=binary_path,
            rewrite=rewrite,
            paths=paths,
            globs=globs,
            update_all=not dry_run,  # dry_run=False 时实际修改
            logger=self.logger,
        )

        # 格式化结果
        return format_replace_result(result, dry_run)
