"""
LSP (Language Server Protocol) 协议类型定义

基于 LSP 3.17 规范
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel


# ============ 基础类型 ============


class Position(BaseModel):
    """位置"""
    line: int  # 0-indexed
    character: int  # 0-indexed (UTF-16 code units)


class Range(BaseModel):
    """范围"""
    start: Position
    end: Position


class Location(BaseModel):
    """位置（文件 + 范围）"""
    uri: str  # file:// URI
    range: Range


class LocationLink(BaseModel):
    """位置链接"""
    originSelectionRange: Range | None = None
    targetUri: str
    targetRange: Range
    targetSelectionRange: Range


# ============ 文档类型 ============


class TextDocumentIdentifier(BaseModel):
    """文档标识"""
    uri: str


class TextDocumentPositionParams(BaseModel):
    """文档位置参数"""
    textDocument: TextDocumentIdentifier
    position: Position


class TextEdit(BaseModel):
    """文本编辑"""
    range: Range
    newText: str


class AnnotatedTextEdit(TextEdit):
    """带注释的文本编辑"""
    annotationId: str


class TextDocumentEdit(BaseModel):
    """文档编辑"""
    textDocument: TextDocumentIdentifier
    edits: list[TextEdit]


# ============ 符号类型 ============


class SymbolKind(int, Enum):
    """符号类型"""
    File = 1
    Module = 2
    Namespace = 3
    Package = 4
    Class = 5
    Method = 6
    Property = 7
    Field = 8
    Constructor = 9
    Enum = 10
    Interface = 11
    Function = 12
    Variable = 13
    Constant = 14
    String = 15
    Number = 16
    Boolean = 17
    Array = 18
    Object = 19
    Key = 20
    Null = 21
    EnumMember = 22
    Struct = 23
    Event = 24
    Operator = 25
    TypeParameter = 26


class SymbolTag(int, Enum):
    """符号标签"""
    Deprecated = 1


@dataclass
class SymbolInformation:
    """符号信息"""
    name: str
    kind: SymbolKind
    location: Location
    containerName: str | None = None
    tags: list[SymbolTag] = field(default_factory=list)
    deprecated: bool = False


@dataclass
class DocumentSymbol:
    """文档符号（带层级）"""
    name: str
    kind: SymbolKind
    range: Range
    selectionRange: Range
    detail: str | None = None
    children: list["DocumentSymbol"] = field(default_factory=list)
    tags: list[SymbolTag] = field(default_factory=list)
    deprecated: bool = False


# ============ 补全类型 ============


class CompletionItemKind(int, Enum):
    """补全项类型"""
    Text = 1
    Method = 2
    Function = 3
    Constructor = 4
    Field = 5
    Variable = 6
    Class = 7
    Interface = 8
    Module = 9
    Property = 10
    Unit = 11
    Value = 12
    Enum = 13
    Keyword = 14
    Snippet = 15
    Color = 16
    File = 17
    Reference = 18
    Folder = 19
    EnumMember = 20
    Constant = 21
    Struct = 22
    Event = 23
    Operator = 24
    TypeParameter = 25


class InsertTextFormat(int, Enum):
    """插入文本格式"""
    PlainText = 1
    Snippet = 2


@dataclass
class CompletionItem:
    """补全项"""
    label: str
    kind: CompletionItemKind | None = None
    detail: str | None = None
    documentation: str | None = None
    insertText: str | None = None
    insertTextFormat: InsertTextFormat = InsertTextFormat.PlainText
    sortText: str | None = None
    filterText: str | None = None


@dataclass
class CompletionList:
    """补全列表"""
    isIncomplete: bool
    items: list[CompletionItem]


# ============ 诊断类型 ============


class DiagnosticSeverity(int, Enum):
    """诊断严重程度"""
    Error = 1
    Warning = 2
    Information = 3
    Hint = 4


class DiagnosticTag(int, Enum):
    """诊断标签"""
    Unnecessary = 1
    Deprecated = 2


@dataclass
class DiagnosticRelatedInformation:
    """诊断相关信息"""
    location: Location
    message: str


@dataclass
class Diagnostic:
    """诊断"""
    range: Range
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.Error
    code: str | int | None = None
    source: str | None = None
    tags: list[DiagnosticTag] = field(default_factory=list)
    relatedInformation: list[DiagnosticRelatedInformation] = field(default_factory=list)


# ============ 悬停类型 ============


class MarkupKind(str, Enum):
    """标记类型"""
    PlainText = "plaintext"
    Markdown = "markdown"


@dataclass
class MarkupContent:
    """标记内容"""
    kind: MarkupKind
    value: str


@dataclass
class Hover:
    """悬停信息"""
    contents: MarkupContent | str | list[str]
    range: Range | None = None


# ============ 工作区类型 ============


@dataclass
class WorkspaceFolder:
    """工作区文件夹"""
    uri: str
    name: str


# ============ 能力声明 ============


@dataclass
class ClientCapabilities:
    """客户端能力"""
    textDocument: dict[str, Any] = field(default_factory=dict)
    workspace: dict[str, Any] = field(default_factory=dict)
    general: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServerCapabilities:
    """服务器能力"""
    textDocumentSync: int | dict[str, Any] | None = None
    completionProvider: dict[str, Any] | None = None
    hoverProvider: bool = True
    signatureHelpProvider: dict[str, Any] | None = None
    definitionProvider: bool = True
    referencesProvider: bool = True
    documentHighlightProvider: bool = True
    documentSymbolProvider: bool = True
    workspaceSymbolProvider: bool = True
    codeActionProvider: bool | dict[str, Any] = True
    renameProvider: bool | dict[str, Any] = True
    executeCommandProvider: dict[str, Any] | None = None


# ============ 服务器配置 ============


@dataclass
class LSPServerConfig:
    """LSP 服务器配置"""
    language: str
    command: list[str]
    extensions: list[str]
    initialization_options: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None


# 预定义的 LSP 服务器配置
LSP_SERVER_CONFIGS: dict[str, LSPServerConfig] = {
    "python": LSPServerConfig(
        language="python",
        command=["pylsp"],
        extensions=[".py", ".pyi", ".pyw"],
        initialization_options={},
    ),
    "pyright": LSPServerConfig(
        language="python",
        command=["pyright", "--output-json"],
        extensions=[".py", ".pyi", ".pyw"],
    ),
    "ruff": LSPServerConfig(
        language="python",
        command=["ruff", "server"],
        extensions=[".py", ".pyi", ".pyw"],
    ),
    "typescript": LSPServerConfig(
        language="typescript",
        command=["typescript-language-server", "--stdio"],
        extensions=[".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"],
    ),
    "gopls": LSPServerConfig(
        language="go",
        command=["gopls"],
        extensions=[".go"],
    ),
    "rust": LSPServerConfig(
        language="rust",
        command=["rust-analyzer"],
        extensions=[".rs"],
    ),
    "cpp": LSPServerConfig(
        language="cpp",
        command=["clangd"],
        extensions=[".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx"],
    ),
    "java": LSPServerConfig(
        language="java",
        command=["jdtls"],
        extensions=[".java"],
    ),
    "csharp": LSPServerConfig(
        language="csharp",
        command=["omnisharp", "-lsp"],
        extensions=[".cs"],
    ),
    "ruby": LSPServerConfig(
        language="ruby",
        command=["solargraph", "stdio"],
        extensions=[".rb", ".rake", ".gemspec"],
    ),
    "php": LSPServerConfig(
        language="php",
        command=["intelephense", "--stdio"],
        extensions=[".php"],
    ),
    "lua": LSPServerConfig(
        language="lua",
        command=["lua-language-server"],
        extensions=[".lua"],
    ),
    "json": LSPServerConfig(
        language="json",
        command=["vscode-json-languageserver", "--stdio"],
        extensions=[".json", ".jsonc"],
    ),
    "yaml": LSPServerConfig(
        language="yaml",
        command=["yaml-language-server", "--stdio"],
        extensions=[".yaml", ".yml"],
    ),
    "dockerfile": LSPServerConfig(
        language="dockerfile",
        command=["docker-langserver", "--stdio"],
        extensions=["Dockerfile", ".dockerfile"],
    ),
    "bash": LSPServerConfig(
        language="bash",
        command=["bash-language-server", "start"],
        extensions=[".sh", ".bash"],
    ),
}
