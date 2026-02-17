"""
CodeSearch 配置模块

定义 CodeSearch 专用配置
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class CodeSearchConfig:
    """CodeSearch 配置"""

    # 基础配置
    enabled: bool = True
    database_path: str = "data/codesearch.db"

    # LSP 集成
    use_lsp: bool = True
    lsp_timeout: int = 30

    # 索引配置
    index_on_startup: bool = False
    index_timeout: int = 300
    max_file_size_kb: int = 500
    max_workers: int = 4

    # 搜索配置
    max_results: int = 100
    cache_size: int = 1000
    context_lines: int = 3

    # 排除模式
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "node_modules/**",
        ".git/**",
        "__pycache__/**",
        "*.pyc",
        "venv/**",
        ".venv/**",
        "dist/**",
        "build/**",
        "*.min.js",
        "*.min.css",
        ".idea/**",
        ".vscode/**",
        "*.egg-info/**",
    ])

    # 包含模式
    include_patterns: list[str] = field(default_factory=lambda: [
        "*.py",
        "*.ts",
        "*.tsx",
        "*.js",
        "*.jsx",
        "*.go",
        "*.rs",
        "*.java",
        "*.c",
        "*.cpp",
        "*.h",
        "*.hpp",
    ])

    # 日志级别
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @classmethod
    def from_dict(cls, data: dict) -> "CodeSearchConfig":
        """从字典创建配置"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "database_path": self.database_path,
            "use_lsp": self.use_lsp,
            "lsp_timeout": self.lsp_timeout,
            "index_on_startup": self.index_on_startup,
            "index_timeout": self.index_timeout,
            "max_file_size_kb": self.max_file_size_kb,
            "max_workers": self.max_workers,
            "max_results": self.max_results,
            "cache_size": self.cache_size,
            "context_lines": self.context_lines,
            "exclude_patterns": self.exclude_patterns,
            "include_patterns": self.include_patterns,
            "log_level": self.log_level,
        }

    def get_database_path(self, base_dir: Path | str) -> Path:
        """获取完整数据库路径"""
        base = Path(base_dir)
        db_path = Path(self.database_path)
        if db_path.is_absolute():
            return db_path
        return base / db_path

    def should_index_file(self, file_path: Path) -> bool:
        """检查文件是否应该被索引"""
        import fnmatch

        # 检查排除模式
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(str(file_path), pattern):
                return False
            # 也检查文件名
            if fnmatch.fnmatch(file_path.name, pattern.replace("/**", "")):
                return False

        # 检查包含模式
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(file_path.name, pattern):
                return True

        return False

    def matches_language(self, file_path: Path) -> str | None:
        """获取文件对应的语言"""
        ext_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
        }
        return ext_map.get(file_path.suffix.lower())
