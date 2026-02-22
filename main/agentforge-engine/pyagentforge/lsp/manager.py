"""
LSP 管理器

管理多个 LSP 客户端实例
"""

import asyncio
from pathlib import Path
from typing import Any, Callable

from pyagentforge.lsp.protocol import (
    Diagnostic,
    LSPServerConfig,
    LSP_SERVER_CONFIGS,
)
from pyagentforge.lsp.client import LSPClient, LSPError
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class LSPManager:
    """
    LSP 管理器

    管理多个语言的 LSP 客户端
    """

    def __init__(
        self,
        workspace_root: str | Path | None = None,
    ) -> None:
        """
        初始化 LSP 管理器

        Args:
            workspace_root: 工作区根目录
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._clients: dict[str, LSPClient] = {}
        self._file_to_client: dict[str, str] = {}  # 文件路径 -> 语言

        # 诊断处理器
        self._diagnostics_handler: Callable[[str, list[Diagnostic]], None] | None = None

    async def start_client(
        self,
        language: str,
        config: LSPServerConfig | None = None,
    ) -> LSPClient | None:
        """
        启动指定语言的 LSP 客户端

        Args:
            language: 语言名称
            config: 服务器配置（可选，使用默认配置）

        Returns:
            LSP 客户端实例
        """
        if language in self._clients:
            return self._clients[language]

        # 获取配置
        if config is None:
            config = LSP_SERVER_CONFIGS.get(language)
            if config is None:
                logger.error(
                    "No LSP server config for language",
                    extra_data={"language": language},
                )
                return None

        # 创建客户端
        client = LSPClient(config, self.workspace_root)

        # 设置诊断处理器
        client._diagnostics_handler = self._handle_diagnostics

        # 启动
        if not await client.start():
            logger.error(
                "Failed to start LSP client",
                extra_data={"language": language},
            )
            return None

        # 初始化
        if not await client.initialize():
            await client.stop()
            logger.error(
                "Failed to initialize LSP client",
                extra_data={"language": language},
            )
            return None

        self._clients[language] = client

        logger.info(
            "LSP client started",
            extra_data={"language": language},
        )

        return client

    async def stop_client(self, language: str) -> None:
        """停止指定语言的 LSP 客户端"""
        if language in self._clients:
            await self._clients[language].stop()
            del self._clients[language]

    async def stop_all(self) -> None:
        """停止所有 LSP 客户端"""
        for language in list(self._clients.keys()):
            await self.stop_client(language)

    def get_client(self, language: str) -> LSPClient | None:
        """获取指定语言的 LSP 客户端"""
        return self._clients.get(language)

    def get_client_for_file(self, file_path: str | Path) -> LSPClient | None:
        """根据文件扩展名获取对应的 LSP 客户端"""
        ext = Path(file_path).suffix.lower()

        # 查找匹配的语言
        for language, config in LSP_SERVER_CONFIGS.items():
            if ext in config.extensions:
                return self._clients.get(language)

        return None

    def detect_language(self, file_path: str | Path) -> str | None:
        """检测文件语言"""
        ext = Path(file_path).suffix.lower()

        for language, config in LSP_SERVER_CONFIGS.items():
            if ext in config.extensions:
                return config.language

        return None

    async def ensure_client_for_file(
        self,
        file_path: str | Path,
        auto_start: bool = True,
    ) -> LSPClient | None:
        """
        确保文件有对应的 LSP 客户端

        Args:
            file_path: 文件路径
            auto_start: 是否自动启动

        Returns:
            LSP 客户端
        """
        language = self.detect_language(file_path)
        if not language:
            return None

        client = self._clients.get(language)
        if client:
            return client

        if auto_start:
            return await self.start_client(language)

        return None

    # ============ 便捷方法 ============

    async def open_file(self, file_path: str | Path) -> bool:
        """
        打开文件

        Args:
            file_path: 文件路径

        Returns:
            是否成功
        """
        client = await self.ensure_client_for_file(file_path)
        if not client:
            return False

        try:
            await client.did_open(file_path)
            return True
        except Exception as e:
            logger.error(
                "Failed to open file in LSP",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return False

    async def close_file(self, file_path: str | Path) -> None:
        """关闭文件"""
        client = self.get_client_for_file(file_path)
        if client:
            await client.did_close(file_path)

    async def goto_definition(
        self,
        file_path: str | Path,
        line: int,
        character: int,
    ) -> list[Any]:
        """
        跳转到定义

        Args:
            file_path: 文件路径
            line: 行号 (0-indexed)
            character: 列号 (0-indexed)

        Returns:
            定义位置列表
        """
        from pyagentforge.lsp.protocol import Position

        client = await self.ensure_client_for_file(file_path)
        if not client:
            return []

        try:
            # 确保文件已打开
            await client.did_open(file_path)

            return await client.goto_definition(
                file_path,
                Position(line=line, character=character),
            )
        except Exception as e:
            logger.error(
                "goto_definition failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return []

    async def find_references(
        self,
        file_path: str | Path,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> list[Any]:
        """
        查找引用

        Args:
            file_path: 文件路径
            line: 行号 (0-indexed)
            character: 列号 (0-indexed)
            include_declaration: 是否包含声明

        Returns:
            引用位置列表
        """
        from pyagentforge.lsp.protocol import Position

        client = await self.ensure_client_for_file(file_path)
        if not client:
            return []

        try:
            await client.did_open(file_path)

            return await client.find_references(
                file_path,
                Position(line=line, character=character),
                include_declaration,
            )
        except Exception as e:
            logger.error(
                "find_references failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return []

    async def hover(
        self,
        file_path: str | Path,
        line: int,
        character: int,
    ) -> Any:
        """
        获取悬停信息

        Args:
            file_path: 文件路径
            line: 行号 (0-indexed)
            character: 列号 (0-indexed)

        Returns:
            悬停信息
        """
        from pyagentforge.lsp.protocol import Position

        client = await self.ensure_client_for_file(file_path)
        if not client:
            return None

        try:
            await client.did_open(file_path)

            return await client.hover(
                file_path,
                Position(line=line, character=character),
            )
        except Exception as e:
            logger.error(
                "hover failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return None

    async def completion(
        self,
        file_path: str | Path,
        line: int,
        character: int,
    ) -> list[Any]:
        """
        获取补全列表

        Args:
            file_path: 文件路径
            line: 行号 (0-indexed)
            character: 列号 (0-indexed)

        Returns:
            补全项列表
        """
        from pyagentforge.lsp.protocol import Position

        client = await self.ensure_client_for_file(file_path)
        if not client:
            return []

        try:
            await client.did_open(file_path)

            result = await client.completion(
                file_path,
                Position(line=line, character=character),
            )

            return result.items
        except Exception as e:
            logger.error(
                "completion failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return []

    async def document_symbols(
        self,
        file_path: str | Path,
    ) -> list[Any]:
        """
        获取文档符号

        Args:
            file_path: 文件路径

        Returns:
            符号列表
        """
        client = await self.ensure_client_for_file(file_path)
        if not client:
            return []

        try:
            await client.did_open(file_path)

            return await client.document_symbols(file_path)
        except Exception as e:
            logger.error(
                "document_symbols failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return []

    async def workspace_symbols(
        self,
        query: str,
        language: str | None = None,
    ) -> list[Any]:
        """
        工作区符号搜索

        Args:
            query: 搜索查询
            language: 限定语言（可选）

        Returns:
            符号列表
        """
        clients = []
        if language:
            client = self._clients.get(language)
            if client:
                clients.append(client)
        else:
            clients.extend(self._clients.values())

        results = []
        for client in clients:
            try:
                symbols = await client.workspace_symbols(query)
                results.extend(symbols)
            except Exception as e:
                logger.error(
                    "workspace_symbols failed",
                    extra_data={"language": client.config.language, "error": str(e)},
                )

        return results

    async def rename(
        self,
        file_path: str | Path,
        line: int,
        character: int,
        new_name: str,
    ) -> dict[str, Any] | None:
        """
        重命名符号

        Args:
            file_path: 文件路径
            line: 行号 (0-indexed)
            character: 列号 (0-indexed)
            new_name: 新名称

        Returns:
            工作区编辑
        """
        from pyagentforge.lsp.protocol import Position

        client = await self.ensure_client_for_file(file_path)
        if not client:
            return None

        try:
            await client.did_open(file_path)

            return await client.rename(
                file_path,
                Position(line=line, character=character),
                new_name,
            )
        except Exception as e:
            logger.error(
                "rename failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return None

    async def format(
        self,
        file_path: str | Path,
        tab_size: int = 4,
        insert_spaces: bool = True,
    ) -> list[Any]:
        """
        格式化文档

        Args:
            file_path: 文件路径
            tab_size: Tab 大小
            insert_spaces: 是否使用空格

        Returns:
            文本编辑列表
        """
        client = await self.ensure_client_for_file(file_path)
        if not client:
            return []

        try:
            await client.did_open(file_path)

            return await client.formatting(file_path, tab_size, insert_spaces)
        except Exception as e:
            logger.error(
                "format failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return []

    def set_diagnostics_handler(
        self,
        handler: Callable[[str, list[Diagnostic]], None],
    ) -> None:
        """设置诊断处理器"""
        self._diagnostics_handler = handler

    def _handle_diagnostics(
        self,
        uri: str,
        diagnostics: list[Diagnostic],
    ) -> None:
        """处理诊断通知"""
        if self._diagnostics_handler:
            self._diagnostics_handler(uri, diagnostics)

    @property
    def active_clients(self) -> dict[str, LSPClient]:
        """获取所有活动的客户端"""
        return self._clients.copy()

    async def __aenter__(self) -> "LSPManager":
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器出口"""
        await self.stop_all()
