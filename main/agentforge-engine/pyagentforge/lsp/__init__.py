"""
LSP (Language Server Protocol) 模块

提供完整的 LSP 客户端实现
"""

from pyagentforge.lsp.client import (
    LSPClient,
    LSPError,
)
from pyagentforge.lsp.manager import (
    LSPManager,
)
from pyagentforge.lsp.protocol import (
    LSP_SERVER_CONFIGS,
    # 能力声明
    ClientCapabilities,
    CompletionItem,
    # 补全类型
    CompletionItemKind,
    CompletionList,
    Diagnostic,
    DiagnosticRelatedInformation,
    # 诊断类型
    DiagnosticSeverity,
    DiagnosticTag,
    DocumentSymbol,
    Hover,
    InsertTextFormat,
    Location,
    LocationLink,
    # 配置
    LSPServerConfig,
    MarkupContent,
    # 悬停类型
    MarkupKind,
    # 基础类型
    Position,
    Range,
    ServerCapabilities,
    SymbolInformation,
    # 符号类型
    SymbolKind,
    SymbolTag,
    TextDocumentEdit,
    # 文档类型
    TextDocumentIdentifier,
    TextEdit,
)

__all__ = [
    # 基础类型
    "Position",
    "Range",
    "Location",
    "LocationLink",
    # 文档类型
    "TextDocumentIdentifier",
    "TextEdit",
    "TextDocumentEdit",
    # 符号类型
    "SymbolKind",
    "SymbolTag",
    "SymbolInformation",
    "DocumentSymbol",
    # 补全类型
    "CompletionItemKind",
    "InsertTextFormat",
    "CompletionItem",
    "CompletionList",
    # 诊断类型
    "DiagnosticSeverity",
    "DiagnosticTag",
    "Diagnostic",
    "DiagnosticRelatedInformation",
    # 悬停类型
    "MarkupKind",
    "MarkupContent",
    "Hover",
    # 能力声明
    "ClientCapabilities",
    "ServerCapabilities",
    # 配置
    "LSPServerConfig",
    "LSP_SERVER_CONFIGS",
    # 客户端
    "LSPClient",
    "LSPError",
    # 管理器
    "LSPManager",
]
