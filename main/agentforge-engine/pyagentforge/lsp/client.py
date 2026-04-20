"""
LSP 客户端实现

与 LSP 服务器进行 JSON-RPC 通信
"""

import asyncio
import contextlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pyagentforge.lsp.protocol import (
    CompletionItem,
    CompletionList,
    Diagnostic,
    DocumentSymbol,
    Hover,
    Location,
    LocationLink,
    LSPServerConfig,
    Position,
    Range,
    ServerCapabilities,
    SymbolInformation,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class LSPError(Exception):
    """LSP 错误"""
    pass


class LSPClient:
    """
    LSP 客户端

    通过 stdio 与 LSP 服务器通信
    """

    def __init__(
        self,
        config: LSPServerConfig,
        workspace_root: str | Path | None = None,
    ) -> None:
        """
        初始化 LSP 客户端

        Args:
            config: LSP 服务器配置
            workspace_root: 工作区根目录
        """
        self.config = config
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

        self._process: asyncio.subprocess.Process | None = None
        self._reader_lock = asyncio.Lock()
        self._writer_lock = asyncio.Lock()
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._capabilities: ServerCapabilities | None = None
        self._initialized = False
        self._shutdown = False

        # 事件处理器
        self._diagnostics_handler: Callable[[str, list[Diagnostic]], None] | None = None
        self._log_handler: Callable[[str], None] | None = None

    @property
    def capabilities(self) -> ServerCapabilities | None:
        """获取服务器能力"""
        return self._capabilities

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    async def start(self) -> bool:
        """
        启动 LSP 服务器进程

        Returns:
            是否启动成功
        """
        try:
            cmd = self.config.command

            # 启动子进程
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace_root),
            )

            # 启动响应读取任务
            self._reader_task = asyncio.create_task(self._read_responses())

            logger.info(
                "LSP server started",
                extra_data={
                    "language": self.config.language,
                    "command": " ".join(cmd),
                    "pid": self._process.pid,
                },
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to start LSP server",
                extra_data={"command": " ".join(cmd), "error": str(e)},
            )
            return False

    async def stop(self) -> None:
        """停止 LSP 服务器"""
        if self._shutdown:
            return

        self._shutdown = True

        # 发送 shutdown 请求
        try:
            await self._send_request("shutdown", {})
            await self._send_notification("exit", {})
        except Exception:
            pass

        # 取消读取任务
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

        # 终止进程
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
            except Exception:
                pass

        self._process = None
        self._initialized = False

        logger.info(
            "LSP server stopped",
            extra_data={"language": self.config.language},
        )

    async def initialize(self) -> bool:
        """
        初始化 LSP 连接

        Returns:
            是否初始化成功
        """
        if self._initialized:
            return True

        if not self._process and not await self.start():
            return False

        # 构建初始化参数
        root_uri = self.workspace_root.as_uri()

        init_params = {
            "processId": os.getpid(),
            "clientInfo": {
                "name": "PyAgentForge",
                "version": "1.0.0",
            },
            "locale": "en",
            "rootPath": str(self.workspace_root),
            "rootUri": root_uri,
            "capabilities": self._build_client_capabilities(),
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": self.workspace_root.name,
                }
            ],
        }

        # 添加初始化选项
        if self.config.initialization_options:
            init_params["initializationOptions"] = self.config.initialization_options

        try:
            response = await self._send_request("initialize", init_params)

            if "result" in response:
                result = response["result"]
                self._capabilities = self._parse_server_capabilities(
                    result.get("capabilities", {})
                )

                # 发送 initialized 通知
                await self._send_notification("initialized", {})

                self._initialized = True

                logger.info(
                    "LSP server initialized",
                    extra_data={
                        "language": self.config.language,
                        "server_name": result.get("serverInfo", {}).get("name", "unknown"),
                    },
                )

                return True

            return False

        except Exception as e:
            logger.error(
                "LSP initialization failed",
                extra_data={"error": str(e)},
            )
            return False

    async def shutdown(self) -> None:
        """关闭 LSP 连接"""
        await self.stop()

    # ============ 文档同步 ============

    async def did_open(
        self,
        file_path: str | Path,
        language_id: str | None = None,
        version: int = 1,
    ) -> None:
        """
        通知服务器文档已打开

        Args:
            file_path: 文件路径
            language_id: 语言 ID
            version: 文档版本
        """
        path = Path(file_path)
        uri = path.as_uri()

        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            logger.error(
                "Failed to read file for didOpen",
                extra_data={"file": str(path), "error": str(e)},
            )
            return

        await self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": language_id or self.config.language,
                "version": version,
                "text": text,
            }
        })

    async def did_close(self, file_path: str | Path) -> None:
        """通知服务器文档已关闭"""
        uri = Path(file_path).as_uri()

        await self._send_notification("textDocument/didClose", {
            "textDocument": {"uri": uri}
        })

    async def did_change(
        self,
        file_path: str | Path,
        content: str,
        version: int = 2,
    ) -> None:
        """
        通知服务器文档已更改

        Args:
            file_path: 文件路径
            content: 新内容
            version: 文档版本
        """
        uri = Path(file_path).as_uri()

        await self._send_notification("textDocument/didChange", {
            "textDocument": {
                "uri": uri,
                "version": version,
            },
            "contentChanges": [{"text": content}],
        })

    async def did_save(self, file_path: str | Path, text: str | None = None) -> None:
        """通知服务器文档已保存"""
        uri = Path(file_path).as_uri()

        params: dict[str, Any] = {"textDocument": {"uri": uri}}
        if text:
            params["text"] = text

        await self._send_notification("textDocument/didSave", params)

    # ============ 语言功能 ============

    async def goto_definition(
        self,
        file_path: str | Path,
        position: Position,
    ) -> list[Location | LocationLink]:
        """
        跳转到定义

        Args:
            file_path: 文件路径
            position: 位置

        Returns:
            定义位置列表
        """
        uri = Path(file_path).as_uri()

        response = await self._send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": position.line, "character": position.character},
        })

        return self._parse_locations(response.get("result"))

    async def find_references(
        self,
        file_path: str | Path,
        position: Position,
        include_declaration: bool = True,
    ) -> list[Location]:
        """
        查找引用

        Args:
            file_path: 文件路径
            position: 位置
            include_declaration: 是否包含声明

        Returns:
            引用位置列表
        """
        uri = Path(file_path).as_uri()

        response = await self._send_request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": position.line, "character": position.character},
            "context": {"includeDeclaration": include_declaration},
        })

        return self._parse_locations(response.get("result"))

    async def hover(
        self,
        file_path: str | Path,
        position: Position,
    ) -> Hover | None:
        """
        获取悬停信息

        Args:
            file_path: 文件路径
            position: 位置

        Returns:
            悬停信息
        """
        uri = Path(file_path).as_uri()

        response = await self._send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": position.line, "character": position.character},
        })

        result = response.get("result")
        if not result:
            return None

        return self._parse_hover(result)

    async def completion(
        self,
        file_path: str | Path,
        position: Position,
        trigger_kind: int = 1,  # Invoked
        trigger_character: str | None = None,
    ) -> CompletionList:
        """
        获取补全列表

        Args:
            file_path: 文件路径
            position: 位置
            trigger_kind: 触发类型
            trigger_character: 触发字符

        Returns:
            补全列表
        """
        uri = Path(file_path).as_uri()

        context: dict[str, Any] = {"triggerKind": trigger_kind}
        if trigger_character:
            context["triggerCharacter"] = trigger_character

        response = await self._send_request("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": position.line, "character": position.character},
            "context": context,
        })

        return self._parse_completion(response.get("result"))

    async def document_symbols(
        self,
        file_path: str | Path,
    ) -> list[DocumentSymbol | SymbolInformation]:
        """
        获取文档符号

        Args:
            file_path: 文件路径

        Returns:
            符号列表
        """
        uri = Path(file_path).as_uri()

        response = await self._send_request("textDocument/documentSymbol", {
            "textDocument": {"uri": uri},
        })

        return self._parse_document_symbols(response.get("result"))

    async def workspace_symbols(
        self,
        query: str,
    ) -> list[SymbolInformation]:
        """
        工作区符号搜索

        Args:
            query: 搜索查询

        Returns:
            符号列表
        """
        response = await self._send_request("workspace/symbol", {
            "query": query,
        })

        return self._parse_symbol_information(response.get("result"))

    async def rename(
        self,
        file_path: str | Path,
        position: Position,
        new_name: str,
    ) -> dict[str, Any] | None:
        """
        重命名符号

        Args:
            file_path: 文件路径
            position: 位置
            new_name: 新名称

        Returns:
            工作区编辑
        """
        uri = Path(file_path).as_uri()

        response = await self._send_request("textDocument/rename", {
            "textDocument": {"uri": uri},
            "position": {"line": position.line, "character": position.character},
            "newName": new_name,
        })

        return response.get("result")

    async def code_action(
        self,
        file_path: str | Path,
        range: Range,
        diagnostics: list[Diagnostic] | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取代码操作

        Args:
            file_path: 文件路径
            range: 范围
            diagnostics: 相关诊断

        Returns:
            代码操作列表
        """
        uri = Path(file_path).as_uri()

        context: dict[str, Any] = {"diagnostics": diagnostics or []}

        response = await self._send_request("textDocument/codeAction", {
            "textDocument": {"uri": uri},
            "range": {
                "start": {"line": range.start.line, "character": range.start.character},
                "end": {"line": range.end.line, "character": range.end.character},
            },
            "context": context,
        })

        return response.get("result", [])

    async def formatting(
        self,
        file_path: str | Path,
        tab_size: int = 4,
        insert_spaces: bool = True,
    ) -> list[dict[str, Any]]:
        """
        格式化文档

        Args:
            file_path: 文件路径
            tab_size: Tab 大小
            insert_spaces: 是否使用空格

        Returns:
            文本编辑列表
        """
        uri = Path(file_path).as_uri()

        response = await self._send_request("textDocument/formatting", {
            "textDocument": {"uri": uri},
            "options": {
                "tabSize": tab_size,
                "insertSpaces": insert_spaces,
            },
        })

        return response.get("result", [])

    # ============ 内部方法 ============

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """发送 JSON-RPC 请求"""
        if not self._process or not self._process.stdin:
            raise LSPError("LSP server not running")

        self._request_id += 1
        request_id = self._request_id

        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self._pending_requests[request_id] = future

        request_body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        message = json.dumps(request_body)
        content_length = len(message.encode("utf-8"))

        # LSP 使用 Content-Length 头
        full_message = f"Content-Length: {content_length}\r\n\r\n{message}"

        try:
            self._process.stdin.write(full_message.encode("utf-8"))
            await self._process.stdin.drain()

            logger.debug(
                "LSP request sent",
                extra_data={"method": method, "id": request_id},
            )

            return await asyncio.wait_for(future, timeout=30)

        except TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise LSPError(f"Request timed out: {method}") from None
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise LSPError(f"Request failed: {e}") from e

    async def _send_notification(
        self,
        method: str,
        params: dict[str, Any],
    ) -> None:
        """发送 JSON-RPC 通知"""
        if not self._process or not self._process.stdin:
            raise LSPError("LSP server not running")

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        message = json.dumps(notification)
        content_length = len(message.encode("utf-8"))

        full_message = f"Content-Length: {content_length}\r\n\r\n{message}"

        self._process.stdin.write(full_message.encode("utf-8"))
        await self._process.stdin.drain()

        logger.debug(
            "LSP notification sent",
            extra_data={"method": method},
        )

    async def _read_responses(self) -> None:
        """持续读取 LSP 响应"""
        if not self._process or not self._process.stdout:
            return

        buffer = b""

        try:
            while True:
                # 读取 Content-Length 头
                while b"\r\n\r\n" not in buffer:
                    chunk = await self._process.stdout.read(1024)
                    if not chunk:
                        return
                    buffer += chunk

                # 解析头部
                header_end = buffer.index(b"\r\n\r\n")
                headers = buffer[:header_end].decode("ascii")
                buffer = buffer[header_end + 4:]

                # 解析 Content-Length
                content_length = 0
                for line in headers.split("\r\n"):
                    if line.startswith("Content-Length:"):
                        content_length = int(line.split(":")[1].strip())
                        break

                # 读取消息体
                while len(buffer) < content_length:
                    chunk = await self._process.stdout.read(content_length - len(buffer))
                    if not chunk:
                        return
                    buffer += chunk

                message = buffer[:content_length]
                buffer = buffer[content_length:]

                # 解析 JSON
                try:
                    data = json.loads(message.decode("utf-8"))
                    await self._handle_message(data)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Invalid JSON from LSP server",
                        extra_data={"error": str(e)},
                    )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "LSP reader error",
                extra_data={"error": str(e)},
            )

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """处理 LSP 消息"""
        # 响应
        if "id" in data:
            request_id = data["id"]
            if request_id in self._pending_requests:
                future = self._pending_requests.pop(request_id)
                if not future.done():
                    future.set_result(data)

        # 通知
        elif "method" in data:
            method = data["method"]
            params = data.get("params", {})

            # 处理诊断通知
            if method == "textDocument/publishDiagnostics":
                uri = params.get("uri", "")
                diagnostics = self._parse_diagnostics(params.get("diagnostics", []))
                if self._diagnostics_handler:
                    self._diagnostics_handler(uri, diagnostics)

            # 处理日志通知
            elif method == "window/logMessage":
                message = params.get("message", "")
                if self._log_handler:
                    self._log_handler(message)
                else:
                    logger.debug(f"LSP log: {message}")

    def _build_client_capabilities(self) -> dict[str, Any]:
        """构建客户端能力"""
        return {
            "textDocument": {
                "synchronization": {
                    "dynamicRegistration": False,
                    "willSave": True,
                    "willSaveWaitUntil": False,
                    "didSave": True,
                },
                "completion": {
                    "dynamicRegistration": False,
                    "completionItem": {
                        "snippetSupport": True,
                        "commitCharactersSupport": True,
                        "documentationFormat": ["markdown", "plaintext"],
                        "deprecatedSupport": True,
                        "preselectSupport": True,
                    },
                    "completionItemKind": {"valueSet": list(range(1, 26))},
                    "contextSupport": True,
                },
                "hover": {
                    "dynamicRegistration": False,
                    "contentFormat": ["markdown", "plaintext"],
                },
                "definition": {"dynamicRegistration": False, "linkSupport": True},
                "references": {"dynamicRegistration": False},
                "documentSymbol": {
                    "dynamicRegistration": False,
                    "symbolKind": {"valueSet": list(range(1, 27))},
                    "hierarchicalDocumentSymbolSupport": True,
                },
                "rename": {"dynamicRegistration": False, "prepareSupport": True},
                "codeAction": {
                    "dynamicRegistration": False,
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": [
                                "",
                                "quickfix",
                                "refactor",
                                "refactor.extract",
                                "refactor.inline",
                                "refactor.rewrite",
                                "source",
                                "source.organizeImports",
                            ]
                        }
                    },
                },
                "formatting": {"dynamicRegistration": False},
            },
            "workspace": {
                "symbol": {
                    "dynamicRegistration": False,
                    "symbolKind": {"valueSet": list(range(1, 27))},
                },
                "workspaceFolders": True,
            },
        }

    def _parse_server_capabilities(
        self,
        caps: dict[str, Any],
    ) -> ServerCapabilities:
        """解析服务器能力"""
        return ServerCapabilities(
            textDocumentSync=caps.get("textDocumentSync"),
            completionProvider=caps.get("completionProvider"),
            hoverProvider=caps.get("hoverProvider", True),
            definitionProvider=caps.get("definitionProvider", True),
            referencesProvider=caps.get("referencesProvider", True),
            documentSymbolProvider=caps.get("documentSymbolProvider", True),
            workspaceSymbolProvider=caps.get("workspaceSymbolProvider", True),
            renameProvider=caps.get("renameProvider", True),
            codeActionProvider=caps.get("codeActionProvider", True),
        )

    def _parse_locations(
        self,
        result: Any,
    ) -> list[Location | LocationLink]:
        """解析位置结果"""
        if not result:
            return []
        if isinstance(result, list):
            locations = []
            for item in result:
                if "uri" in item:
                    locations.append(Location(
                        uri=item["uri"],
                        range=Range(
                            start=Position(
                                line=item["range"]["start"]["line"],
                                character=item["range"]["start"]["character"],
                            ),
                            end=Position(
                                line=item["range"]["end"]["line"],
                                character=item["range"]["end"]["character"],
                            ),
                        ),
                    ))
            return locations
        return []

    def _parse_hover(self, result: dict[str, Any]) -> Hover:
        """解析悬停结果"""
        contents = result.get("contents", "")
        range_data = result.get("range")

        hover_range = None
        if range_data:
            hover_range = Range(
                start=Position(
                    line=range_data["start"]["line"],
                    character=range_data["start"]["character"],
                ),
                end=Position(
                    line=range_data["end"]["line"],
                    character=range_data["end"]["character"],
                ),
            )

        return Hover(contents=contents, range=hover_range)

    def _parse_completion(self, result: Any) -> CompletionList:
        """解析补全结果"""
        if not result:
            return CompletionList(isIncomplete=False, items=[])

        if isinstance(result, list):
            items = [self._parse_completion_item(item) for item in result]
            return CompletionList(isIncomplete=False, items=items)

        items = [
            self._parse_completion_item(item)
            for item in result.get("items", [])
        ]
        return CompletionList(
            isIncomplete=result.get("isIncomplete", False),
            items=items,
        )

    def _parse_completion_item(self, item: dict[str, Any]) -> CompletionItem:
        """解析补全项"""
        return CompletionItem(
            label=item.get("label", ""),
            kind=item.get("kind"),
            detail=item.get("detail"),
            documentation=item.get("documentation"),
            insertText=item.get("insertText"),
            sortText=item.get("sortText"),
            filterText=item.get("filterText"),
        )

    def _parse_document_symbols(
        self,
        result: Any,
    ) -> list[DocumentSymbol | SymbolInformation]:
        """解析文档符号"""
        if not result:
            return []

        symbols = []
        for item in result:
            if "range" in item and "selectionRange" in item:
                # DocumentSymbol
                symbols.append(self._parse_document_symbol(item))
            elif "location" in item:
                # SymbolInformation
                symbols.append(self._parse_symbol_info(item))

        return symbols

    def _parse_document_symbol(self, item: dict[str, Any]) -> DocumentSymbol:
        """解析文档符号"""
        from pyagentforge.lsp.protocol import SymbolKind

        return DocumentSymbol(
            name=item.get("name", ""),
            kind=SymbolKind(item.get("kind", 1)),
            range=Range(
                start=Position(
                    line=item["range"]["start"]["line"],
                    character=item["range"]["start"]["character"],
                ),
                end=Position(
                    line=item["range"]["end"]["line"],
                    character=item["range"]["end"]["character"],
                ),
            ),
            selectionRange=Range(
                start=Position(
                    line=item["selectionRange"]["start"]["line"],
                    character=item["selectionRange"]["start"]["character"],
                ),
                end=Position(
                    line=item["selectionRange"]["end"]["line"],
                    character=item["selectionRange"]["end"]["character"],
                ),
            ),
            detail=item.get("detail"),
            children=[
                self._parse_document_symbol(child)
                for child in item.get("children", [])
            ],
        )

    def _parse_symbol_info(self, item: dict[str, Any]) -> SymbolInformation:
        """解析符号信息"""
        from pyagentforge.lsp.protocol import SymbolKind

        loc = item.get("location", {})
        return SymbolInformation(
            name=item.get("name", ""),
            kind=SymbolKind(item.get("kind", 1)),
            location=Location(
                uri=loc.get("uri", ""),
                range=Range(
                    start=Position(
                        line=loc["range"]["start"]["line"],
                        character=loc["range"]["start"]["character"],
                    ),
                    end=Position(
                        line=loc["range"]["end"]["line"],
                        character=loc["range"]["end"]["character"],
                    ),
                ),
            ),
            containerName=item.get("containerName"),
        )

    def _parse_symbol_information(
        self,
        result: Any,
    ) -> list[SymbolInformation]:
        """解析符号信息列表"""
        if not result:
            return []
        return [self._parse_symbol_info(item) for item in result]

    def _parse_diagnostics(
        self,
        items: list[dict[str, Any]],
    ) -> list[Diagnostic]:
        """解析诊断列表"""
        from pyagentforge.lsp.protocol import DiagnosticSeverity

        diagnostics = []
        for item in items:
            diag = Diagnostic(
                range=Range(
                    start=Position(
                        line=item["range"]["start"]["line"],
                        character=item["range"]["start"]["character"],
                    ),
                    end=Position(
                        line=item["range"]["end"]["line"],
                        character=item["range"]["end"]["character"],
                    ),
                ),
                message=item.get("message", ""),
                severity=DiagnosticSeverity(item.get("severity", 1)),
                code=item.get("code"),
                source=item.get("source"),
            )
            diagnostics.append(diag)

        return diagnostics
