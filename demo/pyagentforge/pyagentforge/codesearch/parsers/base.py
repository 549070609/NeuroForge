"""
CodeSearch 解析器基类

定义解析器接口和注册表
"""

from abc import ABC, abstractmethod
from pathlib import Path

from pyagentforge.codesearch.storage.models import Symbol


class BaseParser(ABC):
    """代码解析器基类"""

    @abstractmethod
    async def parse_file(self, content: str, file_path: Path) -> list[Symbol]:
        """
        解析文件内容, 提取符号

        Args:
            content: 文件内容
            file_path: 文件路径 (用于确定语言)

        Returns:
            提取的符号列表
        """
        pass

    @abstractmethod
    def supports_language(self, language: str) -> bool:
        """
        检查是否支持指定语言

        Args:
            language: 语言名称

        Returns:
            是否支持
        """
        pass

    @property
    def priority(self) -> int:
        """
        解析器优先级 (数字越大优先级越高)
        - AST 解析器: 100
        - Tree-sitter: 80
        - 正则解析器: 10
        """
        return 50


class ParserRegistry:
    """解析器注册表"""

    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        """注册解析器"""
        self._parsers.append(parser)
        self._parsers.sort(key=lambda p: p.priority, reverse=True)

    def get_parser(self, language: str) -> BaseParser | None:
        """获取支持指定语言的最高优先级解析器"""
        for parser in self._parsers:
            if parser.supports_language(language):
                return parser
        return None

    def get_all_parsers(self) -> list[BaseParser]:
        """获取所有已注册的解析器"""
        return self._parsers.copy()
