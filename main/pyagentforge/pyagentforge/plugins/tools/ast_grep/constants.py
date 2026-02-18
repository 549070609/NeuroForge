"""
AST-Grep 插件常量配置
"""

# 支持的语言列表 (25种)
CLI_LANGUAGES = frozenset([
    "bash",
    "c",
    "cpp",
    "csharp",
    "css",
    "elixir",
    "go",
    "haskell",
    "html",
    "java",
    "javascript",
    "json",
    "kotlin",
    "lua",
    "nix",
    "php",
    "python",
    "ruby",
    "rust",
    "scala",
    "solidity",
    "swift",
    "typescript",
    "tsx",
    "yaml",
])

# 语言扩展名映射
LANG_EXTENSIONS = {
    "bash": [".bash", ".sh", ".zsh", ".bats"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".h"],
    "csharp": [".cs"],
    "css": [".css"],
    "elixir": [".ex", ".exs"],
    "go": [".go"],
    "haskell": [".hs", ".lhs"],
    "html": [".html", ".htm"],
    "java": [".java"],
    "javascript": [".js", ".jsx", ".mjs", ".cjs"],
    "json": [".json"],
    "kotlin": [".kt", ".kts"],
    "lua": [".lua"],
    "nix": [".nix"],
    "php": [".php"],
    "python": [".py", ".pyi"],
    "ruby": [".rb", ".rake"],
    "rust": [".rs"],
    "scala": [".scala", ".sc"],
    "solidity": [".sol"],
    "swift": [".swift"],
    "typescript": [".ts", ".cts", ".mts"],
    "tsx": [".tsx"],
    "yaml": [".yaml", ".yml"],
}

# 超时配置 (毫秒)
DEFAULT_TIMEOUT_MS = 300_000  # 5 分钟

# 最大输出字节数
DEFAULT_MAX_OUTPUT_BYTES = 1 * 1024 * 1024  # 1MB

# 最大匹配数
DEFAULT_MAX_MATCHES = 500

# 命令名称
CLI_NAME = "sg"
CLI_PACKAGE_NAME = "ast-grep-cli"
