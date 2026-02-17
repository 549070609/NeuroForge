"""
LSP 工具

语言服务协议支持，提供代码智能功能
"""

import asyncio
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker, PermissionResult
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class LSPTool(BaseTool):
    """LSP 工具 - 语言服务协议"""

    name = "lsp"
    description = """语言服务协议工具。

提供代码智能功能:
- goto_definition: 跳转到定义
- find_references: 查找引用
- rename: 重命名符号
- hover: 获取类型信息
- completion: 代码补全
- document_symbols: 文档符号列表
- workspace_symbols: 工作区符号搜索
- format: 格式化文档
- diagnostics: 获取诊断信息

支持多种语言: Python, TypeScript, Go, Rust, C++, Java, C#, Ruby, PHP, Lua, JSON, YAML 等

注意: 需要安装对应的 LSP 服务器:
- Python: pip install python-lsp-server
- TypeScript: npm install -g typescript-language-server
- Go: go install golang.org/x/tools/gopls@latest
- Rust: rustup component add rust-analyzer
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "goto_definition",
                    "find_references",
                    "rename",
                    "hover",
                    "completion",
                    "document_symbols",
                    "workspace_symbols",
                    "format",
                    "diagnostics",
                ],
                "description": "要执行的操作",
            },
            "file_path": {
                "type": "string",
                "description": "文件路径",
            },
            "line": {
                "type": "integer",
                "description": "行号 (1-indexed)",
            },
            "column": {
                "type": "integer",
                "description": "列号 (1-indexed)",
            },
            "new_name": {
                "type": "string",
                "description": "新名称 (用于 rename 操作)",
            },
            "query": {
                "type": "string",
                "description": "搜索查询 (用于 workspace_symbols)",
            },
            "language": {
                "type": "string",
                "description": "语言类型 (自动检测如果未指定)",
            },
        },
        "required": ["action", "file_path"],
    }
    timeout = 60
    risk_level = "low"

    # 类变量：共享 LSP 管理器
    _lsp_manager = None
    _manager_lock = asyncio.Lock()

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
        workspace_root: str | None = None,
    ) -> None:
        self.permission_checker = permission_checker
        self.workspace_root = workspace_root or str(Path.cwd())

    async def _get_manager(self) -> "LSPManager":
        """获取或创建 LSP 管理器"""
        from pyagentforge.lsp.manager import LSPManager

        async with LSPTool._manager_lock:
            if LSPTool._lsp_manager is None:
                LSPTool._lsp_manager = LSPManager(self.workspace_root)
            return LSPTool._lsp_manager

    def _detect_language(self, file_path: str) -> str | None:
        """根据文件扩展名检测语言"""
        from pyagentforge.lsp.protocol import LSP_SERVER_CONFIGS

        ext = Path(file_path).suffix.lower()
        for lang, config in LSP_SERVER_CONFIGS.items():
            if ext in config.extensions:
                return config.language
        return None

    async def execute(
        self,
        action: str,
        file_path: str,
        line: int | None = None,
        column: int | None = None,
        new_name: str | None = None,
        query: str | None = None,
        language: str | None = None,
    ) -> str:
        """执行 LSP 操作"""
        logger.info(
            "Executing LSP action",
            extra_data={"action": action, "file_path": file_path},
        )

        path = Path(file_path)

        # 检查权限
        if self.permission_checker:
            if self.permission_checker.check_path(str(path)) == PermissionResult.DENY:
                return f"Error: Access to path '{file_path}' is denied"

        # 检查文件存在（除了 workspace_symbols）
        if action != "workspace_symbols" and not path.exists():
            return f"Error: File '{file_path}' does not exist"

        # 检测语言
        if not language:
            language = self._detect_language(file_path)
            if not language and action != "workspace_symbols":
                return f"Error: Could not detect language for '{file_path}'"

        try:
            manager = await self._get_manager()

            if action == "goto_definition":
                return await self._goto_definition(manager, path, line, column)
            elif action == "find_references":
                return await self._find_references(manager, path, line, column)
            elif action == "hover":
                return await self._hover(manager, path, line, column)
            elif action == "completion":
                return await self._completion(manager, path, line, column)
            elif action == "document_symbols":
                return await self._document_symbols(manager, path)
            elif action == "workspace_symbols":
                return await self._workspace_symbols(manager, query, language)
            elif action == "rename":
                if not new_name:
                    return "Error: new_name is required for rename action"
                return await self._rename(manager, path, line, column, new_name)
            elif action == "format":
                return await self._format(manager, path)
            elif action == "diagnostics":
                return await self._diagnostics(manager, path)
            else:
                return f"Error: Unknown action '{action}'"

        except ImportError as e:
            return f"Error: LSP module not available: {e}"
        except Exception as e:
            logger.error(
                "LSP action error",
                extra_data={"action": action, "error": str(e)},
            )
            return f"Error: {str(e)}"

    async def _goto_definition(
        self,
        manager: Any,
        path: Path,
        line: int | None,
        column: int | None,
    ) -> str:
        """跳转到定义"""
        if line is None:
            return "Error: line number required"

        # LSP 使用 0-indexed
        locations = await manager.goto_definition(
            str(path),
            line - 1,
            (column or 1) - 1,
        )

        if not locations:
            return "No definition found"

        output = ["Definition locations:", "-" * 40]
        for loc in locations:
            if hasattr(loc, 'uri'):
                uri = loc.uri
                range_info = loc.range
                start_line = range_info.start.line + 1  # 转换为 1-indexed
                start_col = range_info.start.character + 1
                output.append(f"  {uri}:{start_line}:{start_col}")
            else:
                output.append(f"  {loc}")

        return "\n".join(output)

    async def _find_references(
        self,
        manager: Any,
        path: Path,
        line: int | None,
        column: int | None,
    ) -> str:
        """查找引用"""
        if line is None:
            return "Error: line number required"

        locations = await manager.find_references(
            str(path),
            line - 1,
            (column or 1) - 1,
        )

        if not locations:
            return "No references found"

        output = [f"Found {len(locations)} references:", "-" * 40]
        for loc in locations:
            if hasattr(loc, 'uri'):
                uri = loc.uri
                range_info = loc.range
                start_line = range_info.start.line + 1
                output.append(f"  {uri}:{start_line}")
            else:
                output.append(f"  {loc}")

        # 限制输出
        if len(output) > 50:
            output = output[:50]
            output.append(f"  ... and {len(locations) - 49} more")

        return "\n".join(output)

    async def _hover(
        self,
        manager: Any,
        path: Path,
        line: int | None,
        column: int | None,
    ) -> str:
        """获取悬停信息"""
        if line is None:
            return "Error: line number required"

        hover = await manager.hover(
            str(path),
            line - 1,
            (column or 1) - 1,
        )

        if not hover:
            return "No hover information available"

        # 解析悬停内容
        content = hover.contents
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return "\n".join(str(item) for item in content)
        elif hasattr(content, 'value'):
            return content.value

        return str(content)

    async def _completion(
        self,
        manager: Any,
        path: Path,
        line: int | None,
        column: int | None,
    ) -> str:
        """代码补全"""
        if line is None or column is None:
            return "Error: line and column required for completion"

        items = await manager.completion(
            str(path),
            line - 1,
            column - 1,
        )

        if not items:
            return "No completions available"

        output = ["Completions:", "-" * 40]
        for item in items[:50]:  # 限制数量
            label = item.label
            kind = item.kind.name if item.kind else "Unknown"
            detail = f" - {item.detail}" if item.detail else ""
            output.append(f"  [{kind:12}] {label}{detail}")

        if len(items) > 50:
            output.append(f"  ... and {len(items) - 50} more")

        return "\n".join(output)

    async def _document_symbols(
        self,
        manager: Any,
        path: Path,
    ) -> str:
        """获取文档符号"""
        symbols = await manager.document_symbols(str(path))

        if not symbols:
            return "No symbols found in document"

        output = [f"Symbols in {path.name}:", "-" * 40]

        def format_symbol(symbol: Any, indent: int = 0) -> None:
            kind = symbol.kind.name if hasattr(symbol.kind, 'name') else str(symbol.kind)
            line = symbol.range.start.line + 1 if hasattr(symbol, 'range') else 0
            prefix = "  " * indent
            output.append(f"{prefix}{kind:12} line {line:4}: {symbol.name}")

            # 递归处理子符号
            if hasattr(symbol, 'children') and symbol.children:
                for child in symbol.children:
                    format_symbol(child, indent + 1)

        for symbol in symbols:
            format_symbol(symbol)

        return "\n".join(output)

    async def _workspace_symbols(
        self,
        manager: Any,
        query: str | None,
        language: str | None,
    ) -> str:
        """工作区符号搜索"""
        if not query:
            return "Error: query is required for workspace_symbols action"

        symbols = await manager.workspace_symbols(query, language)

        if not symbols:
            return f"No symbols found matching '{query}'"

        output = [f"Symbols matching '{query}':", "-" * 40]
        for symbol in symbols[:50]:
            kind = symbol.kind.name if hasattr(symbol.kind, 'name') else str(symbol.kind)
            name = symbol.name
            container = f" ({symbol.containerName})" if symbol.containerName else ""
            uri = symbol.location.uri if hasattr(symbol, 'location') else ""
            output.append(f"  [{kind:12}] {name}{container}")
            if uri:
                output.append(f"    {uri}")

        if len(symbols) > 50:
            output.append(f"  ... and {len(symbols) - 50} more")

        return "\n".join(output)

    async def _rename(
        self,
        manager: Any,
        path: Path,
        line: int | None,
        column: int | None,
        new_name: str,
    ) -> str:
        """重命名符号"""
        if line is None:
            return "Error: line number required"

        workspace_edit = await manager.rename(
            str(path),
            line - 1,
            (column or 1) - 1,
            new_name,
        )

        if not workspace_edit:
            return "Rename not available or no changes needed"

        # 解析工作区编辑
        changes = workspace_edit.get("changes", {})
        if not changes:
            return "No changes to apply"

        output = [f"Rename to '{new_name}':", "-" * 40]
        total_edits = 0

        for uri, edits in changes.items():
            file_path = uri.replace("file://", "")
            output.append(f"\n{file_path}:")
            for edit in edits:
                line_num = edit.get("range", {}).get("start", {}).get("line", 0) + 1
                output.append(f"  Line {line_num}: {edit.get('newText', '')}")
                total_edits += 1

        output.append(f"\nTotal: {total_edits} changes in {len(changes)} files")
        output.append("\nNote: Changes are not automatically applied. Use edit tool to apply.")

        return "\n".join(output)

    async def _format(
        self,
        manager: Any,
        path: Path,
    ) -> str:
        """格式化文档"""
        edits = await manager.format(str(path))

        if not edits:
            return "No formatting changes needed"

        output = ["Formatting changes:", "-" * 40]

        for edit in edits[:20]:
            range_info = edit.get("range", {})
            start = range_info.get("start", {})
            end = range_info.get("end", {})
            new_text = edit.get("newText", "")

            output.append(
                f"  Lines {start.get('line', 0) + 1}-{end.get('line', 0) + 1}: "
                f"{new_text[:50]}{'...' if len(new_text) > 50 else ''}"
            )

        if len(edits) > 20:
            output.append(f"  ... and {len(edits) - 20} more changes")

        output.append("\nNote: Changes are not automatically applied.")

        return "\n".join(output)

    async def _diagnostics(
        self,
        manager: Any,
        path: Path,
    ) -> str:
        """获取诊断信息"""
        # 确保文件已打开
        await manager.open_file(str(path))

        # 等待诊断（LSP 是异步的）
        await asyncio.sleep(1)

        output = [f"Diagnostics for {path.name}:", "-" * 40]
        output.append("Note: Diagnostics are published asynchronously.")
        output.append("Check the logs or wait for diagnostic notifications.")
        output.append("\nTo get real-time diagnostics, use the LSP manager's")
        output.append("set_diagnostics_handler() method.")

        return "\n".join(output)
