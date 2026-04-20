"""
增强版 CodeSearch 工具

集成 AST 解析、增量索引、高级查询语法
"""

from pathlib import Path
from typing import Any

from pyagentforge.codesearch.config import CodeSearchConfig
from pyagentforge.codesearch.indexers.symbol_indexer import SymbolIndexer
from pyagentforge.codesearch.parsers.base import ParserRegistry
from pyagentforge.codesearch.parsers.python_parser import PythonParser
from pyagentforge.codesearch.parsers.regex_parser import RegexParser
from pyagentforge.codesearch.query.executor import QueryExecutor
from pyagentforge.codesearch.query.parser import QueryParser
from pyagentforge.codesearch.storage.database import CodeSearchDatabase
from pyagentforge.codesearch.storage.models import Symbol
from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker, PermissionResult
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CodeSearchTool(BaseTool):
    """增强版 CodeSearch 工具"""

    name = "codesearch"
    description = """语义代码搜索 - 增强版。

比 grep 更智能的代码搜索:
- AST 级别的符号理解
- 支持多种语言 (Python, TypeScript, Go, Rust 等)
- 增量索引, 快速响应
- 高级查询语法

搜索语法:
- "function:xxx" - 搜索函数定义
- "class:xxx" - 搜索类定义
- "xxx AND yyy" - 逻辑 AND
- "xxx OR yyy" - 逻辑 OR
- "NOT test" - 排除
- "xxx*" - 通配符
- "(xxx OR yyy) AND lang:python" - 分组

子命令:
- index <path> - 索引指定路径
- status - 显示索引状态
- clear - 清除索引
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询或子命令 (index/status/clear)",
            },
            "path": {
                "type": "string",
                "description": "搜索/索引路径",
                "default": ".",
            },
            "file_pattern": {
                "type": "string",
                "description": "文件模式 (如 *.py)",
                "default": "*",
            },
            "context_lines": {
                "type": "integer",
                "description": "上下文行数",
                "default": 3,
            },
            "max_results": {
                "type": "integer",
                "description": "最大结果数",
                "default": 50,
            },
        },
        "required": ["query"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(
        self,
        db: CodeSearchDatabase,
        indexer: SymbolIndexer,
        parser_registry: ParserRegistry,
        config: CodeSearchConfig | None = None,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        self.db = db
        self.indexer = indexer
        self.parser_registry = parser_registry
        self.config = config or CodeSearchConfig()
        self.permission_checker = permission_checker
        self._query_cache: dict[str, list[Symbol]] = {}

    async def execute(
        self,
        query: str,
        path: str = ".",
        file_pattern: str = "*",
        context_lines: int = 3,
        max_results: int = 50,
    ) -> str:
        """执行代码搜索或子命令"""
        logger.info(
            "Executing code search",
            extra_data={"query": query, "path": path},
        )

        # 检查子命令
        if query.startswith("index "):
            return await self._handle_index(query[6:].strip(), file_pattern)
        elif query == "status":
            return await self._handle_status()
        elif query == "clear":
            return await self._handle_clear()

        # 普通搜索
        return await self._handle_search(
            query, path, file_pattern, context_lines, max_results
        )

    async def _handle_search(
        self,
        query: str,
        path: str,
        file_pattern: str,
        context_lines: int,
        max_results: int,
    ) -> str:
        """处理搜索请求"""
        search_path = Path(path)

        # 权限检查
        if (
            self.permission_checker
            and self.permission_checker.check_path(str(search_path)) == PermissionResult.DENY
        ):
            return f"Error: Access to path '{path}' is denied"

        # 尝试从缓存获取
        cache_key = f"{query}:{path}:{file_pattern}:{max_results}"
        if cache_key in self._query_cache:
            symbols = self._query_cache[cache_key]
        else:
            symbols = await self._execute_search(
                query, path, file_pattern, max_results
            )
            # 更新缓存
            self._update_cache(cache_key, symbols)

        if not symbols:
            return f"No results found for: {query}"

        # 格式化输出
        return self._format_results(symbols, context_lines)

    async def _execute_search(
        self,
        query: str,
        path: str,
        file_pattern: str,
        max_results: int,
    ) -> list[Symbol]:
        """执行搜索"""
        try:
            parser = QueryParser(query)
            ast = parser.parse()
            if ast:
                executor = QueryExecutor(self.db)
                return await executor.execute(ast, path, file_pattern, max_results)
        except Exception as e:
            logger.warning(
                "Query parsing failed, using simple search",
                extra_data={"error": str(e)},
            )

        # 简单搜索回退
        return await self.db.search_symbols(
            name=query,
            file_pattern=path if path != "." else None,
            limit=max_results,
        )

    async def _handle_index(self, path: str, pattern: str) -> str:
        """处理索引子命令"""
        index_path = Path(path)

        if (
            self.permission_checker
            and self.permission_checker.check_path(str(index_path)) == PermissionResult.DENY
        ):
            return f"Error: Access to path '{path}' is denied"

        if not index_path.exists():
            return f"Error: Path '{path}' does not exist"

        count = await self.indexer.index_directory(index_path, pattern)
        return f"Indexed {count} files in '{path}'"

    async def _handle_status(self) -> str:
        """处理状态子命令"""
        stats = await self.db.get_stats()

        lines = [
            "CodeSearch Index Status:",
            f"  Symbols: {stats['symbol_count']}",
            f"  Files indexed: {stats['file_count']}",
            f"  Cache size: {len(self._query_cache)}/{self.config.cache_size}",
            f"  Database: {self.db.db_path}",
        ]
        return "\n".join(lines)

    async def _handle_clear(self) -> str:
        """处理清除子命令"""
        await self.db.clear_all()
        self._query_cache.clear()
        return "Index cleared"

    def _update_cache(self, key: str, symbols: list[Symbol]) -> None:
        """更新查询缓存"""
        if len(self._query_cache) >= self.config.cache_size:
            # 简单 LRU: 删除最旧的条目
            oldest_key = next(iter(self._query_cache))
            del self._query_cache[oldest_key]
        self._query_cache[key] = symbols

    def _format_results(
        self,
        symbols: list[Symbol],
        context_lines: int,
    ) -> str:
        """格式化搜索结果"""
        output = ["Code search results:", "=" * 50]

        for symbol in symbols:
            output.append(f"\n [{symbol.kind.value}] {symbol.name}")
            output.append(f"  File: {symbol.file_path}:{symbol.line_start}")
            if symbol.signature:
                output.append(f"  Signature: {symbol.signature}")
            if symbol.docstring:
                # 截断过长的文档字符串
                doc = symbol.docstring[:100]
                if len(symbol.docstring) > 100:
                    doc += "..."
                output.append(f"  Doc: {doc}")

            # 读取上下文代码
            try:
                context = self._get_code_context(
                    symbol.file_path,
                    symbol.line_start,
                    context_lines,
                )
                if context:
                    output.append("  Context:")
                    for line in context:
                        output.append(f"    {line}")
            except Exception:
                pass

        output.append(f"\n{'=' * 50}")
        output.append(f"Total: {len(symbols)} results")
        return "\n".join(output)

    def _get_code_context(
        self,
        file_path: str,
        line_number: int,
        context_lines: int,
    ) -> list[str]:
        """获取代码上下文"""
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        context = []
        for i in range(start, end):
            prefix = ">" if i == line_number - 1 else " "
            context.append(f"{prefix} {i + 1:4}: {lines[i].rstrip()}")

        return context


def create_codesearch_tool(
    config: CodeSearchConfig | None = None,
    permission_checker: PermissionChecker | None = None,
    workspace_root: str | Path | None = None,
) -> CodeSearchTool:
    """
    创建配置好的 CodeSearchTool 实例

    Args:
        config: CodeSearch 配置
        permission_checker: 权限检查器
        workspace_root: 工作区根目录

    Returns:
        CodeSearchTool 实例
    """
    config = config or CodeSearchConfig()

    # 确定数据库路径
    if workspace_root:
        db_path = config.get_database_path(Path(workspace_root))
    else:
        db_path = Path(config.database_path)

    # 确保目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 初始化数据库
    db = CodeSearchDatabase(str(db_path))

    # 注册解析器
    parser_registry = ParserRegistry()
    parser_registry.register(PythonParser())  # Python AST 解析器
    parser_registry.register(RegexParser())   # 正则回退解析器

    # 创建索引器
    indexer = SymbolIndexer(db=db, parser_registry=parser_registry, config=config)

    return CodeSearchTool(
        db=db,
        indexer=indexer,
        parser_registry=parser_registry,
        config=config,
        permission_checker=permission_checker,
    )
