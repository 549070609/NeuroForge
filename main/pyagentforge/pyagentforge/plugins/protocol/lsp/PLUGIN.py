"""
LSP Integration Plugin

Language Server Protocol (LSP) integration for code intelligence
"""

import logging
from typing import Any, List, Optional

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool


class LSPTool(BaseTool):
    """LSP Tool - Language Server Protocol operations"""

    name = "lsp"
    description = """Language Server Protocol operations.

    Use scenarios:
    - Go to definition
    - Find references
    - Get completions
    - Get hover information
    - Find symbols
    - Get diagnostics

    Provides code intelligence features through LSP.
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["definition", "references", "completion", "hover", "symbols", "diagnostics"],
                "description": "LSP operation to perform",
            },
            "file_path": {
                "type": "string",
                "description": "File path for the operation",
            },
            "line": {
                "type": "integer",
                "description": "Line number (0-indexed)",
            },
            "character": {
                "type": "integer",
                "description": "Character position (0-indexed)",
            },
            "query": {
                "type": "string",
                "description": "Query string for symbol search",
            },
        },
        "required": ["operation"],
    }
    timeout = 30
    risk_level = "low"

    def __init__(self, lsp_plugin: "LSPPlugin" = None):
        self.lsp_plugin = lsp_plugin

    async def execute(
        self,
        operation: str,
        file_path: str = None,
        line: int = None,
        character: int = None,
        query: str = None,
    ) -> str:
        """Execute LSP operation"""
        if not self.lsp_plugin:
            return "Error: LSP plugin not initialized"

        if operation == "definition":
            if not all([file_path, line is not None, character is not None]):
                return "Error: definition requires file_path, line, and character"
            return await self.lsp_plugin.get_definition(file_path, line, character)

        elif operation == "references":
            if not all([file_path, line is not None, character is not None]):
                return "Error: references requires file_path, line, and character"
            return await self.lsp_plugin.get_references(file_path, line, character)

        elif operation == "completion":
            if not all([file_path, line is not None, character is not None]):
                return "Error: completion requires file_path, line, and character"
            return await self.lsp_plugin.get_completions(file_path, line, character)

        elif operation == "hover":
            if not all([file_path, line is not None, character is not None]):
                return "Error: hover requires file_path, line, and character"
            return await self.lsp_plugin.get_hover(file_path, line, character)

        elif operation == "symbols":
            if not query:
                return "Error: symbols requires query parameter"
            return await self.lsp_plugin.find_symbols(query)

        elif operation == "diagnostics":
            if not file_path:
                return "Error: diagnostics requires file_path"
            return await self.lsp_plugin.get_diagnostics(file_path)

        else:
            return f"Error: Unknown operation: {operation}"


class LSPPlugin(Plugin):
    """LSP Integration Protocol Plugin"""

    metadata = PluginMetadata(
        id="protocol.lsp",
        name="LSP Integration",
        version="1.0.0",
        type=PluginType.PROTOCOL,
        description="Language Server Protocol integration for code intelligence features",
        author="PyAgentForge",
        provides=["protocol.lsp"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._clients: dict[str, Any] = {}
        self._lsp_tool: Optional[LSPTool] = None

    async def on_plugin_activate(self) -> None:
        """Activate LSP plugin"""
        await super().on_plugin_activate()
        self._lsp_tool = LSPTool(lsp_plugin=self)
        self.context.logger.info("LSP plugin initialized")

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin and stop all language servers"""
        for language in list(self._clients.keys()):
            await self.stop_language_server(language)
        await super().on_plugin_deactivate()

    async def start_language_server(
        self,
        language: str,
        command: str,
        args: list[str] = None,
    ) -> bool:
        """Start a language server for a specific language

        Args:
            language: Language identifier (e.g., 'python', 'typescript')
            command: Command to start the language server
            args: Optional command arguments

        Returns:
            True if server started successfully
        """
        try:
            self._clients[language] = {
                "command": command,
                "args": args or [],
                "running": True,
            }
            self.context.logger.info(f"Started LSP server for {language}")
            return True
        except Exception as e:
            self.context.logger.error(f"Failed to start LSP server for {language}: {e}")
            return False

    async def stop_language_server(self, language: str) -> bool:
        """Stop a language server"""
        if language in self._clients:
            self._clients[language]["running"] = False
            del self._clients[language]
            self.context.logger.info(f"Stopped LSP server for {language}")
            return True
        return False

    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages"""
        return list(self._clients.keys())

    async def get_definition(self, file_path: str, line: int, character: int) -> str:
        """Get definition location"""
        # Placeholder - would delegate to appropriate language server
        return f"Definition at {file_path}:{line}:{character}"

    async def get_references(self, file_path: str, line: int, character: int) -> str:
        """Find all references"""
        # Placeholder
        return f"References to symbol at {file_path}:{line}:{character}"

    async def get_completions(self, file_path: str, line: int, character: int) -> str:
        """Get code completions"""
        # Placeholder
        return f"Completions at {file_path}:{line}:{character}"

    async def get_hover(self, file_path: str, line: int, character: int) -> str:
        """Get hover information"""
        # Placeholder
        return f"Hover info at {file_path}:{line}:{character}"

    async def find_symbols(self, query: str) -> str:
        """Find symbols matching query"""
        # Placeholder
        return f"Symbols matching: {query}"

    async def get_diagnostics(self, file_path: str) -> str:
        """Get diagnostics for a file"""
        # Placeholder
        return f"Diagnostics for {file_path}"

    def get_tools(self) -> List[BaseTool]:
        """Return plugin provided tools"""
        if self._lsp_tool:
            return [self._lsp_tool]
        return []
