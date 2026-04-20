"""
CodeSearch 模块测试
"""

import tempfile
from pathlib import Path

import pytest

from pyagentforge.codesearch import (
    CodeSearchConfig,
    CodeSearchDatabase,
    PythonParser,
    QueryParser,
    RegexParser,
    create_codesearch_tool,
)
from pyagentforge.codesearch.storage.models import SymbolKind


class TestPythonParser:
    """Python AST 解析器测试"""

    @pytest.fixture
    def parser(self) -> PythonParser:
        return PythonParser()

    @pytest.mark.asyncio
    async def test_parse_simple_function(self, parser: PythonParser):
        """测试解析简单函数"""
        code = '''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"
'''
        symbols = await parser.parse_file(code, Path("test.py"))

        assert len(symbols) == 1
        assert symbols[0].name == "hello"
        assert symbols[0].kind == SymbolKind.FUNCTION
        assert symbols[0].docstring == "Say hello."
        assert "name: str" in symbols[0].signature

    @pytest.mark.asyncio
    async def test_parse_class_with_methods(self, parser: PythonParser):
        """测试解析类和方法"""
        code = '''
class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        return a + b

    async def compute(self, value: int) -> int:
        return value * 2
'''
        symbols = await parser.parse_file(code, Path("calc.py"))

        # 应该有 1 个类 + 2 个方法
        assert len(symbols) == 3

        # 检查类
        classes = [s for s in symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) == 1
        assert classes[0].name == "Calculator"

        # 检查方法
        methods = [s for s in symbols if s.kind == SymbolKind.METHOD]
        assert len(methods) == 2
        method_names = {m.name for m in methods}
        assert "add" in method_names
        assert "compute" in method_names

    @pytest.mark.asyncio
    async def test_parse_async_function(self, parser: PythonParser):
        """测试解析异步函数"""
        code = '''
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    pass
'''
        symbols = await parser.parse_file(code, Path("async_test.py"))

        assert len(symbols) == 1
        assert symbols[0].kind == SymbolKind.ASYNC_FUNCTION
        assert "async def" in symbols[0].signature

    @pytest.mark.asyncio
    async def test_parse_imports(self, parser: PythonParser):
        """测试解析导入语句"""
        code = '''
import os
import sys
from typing import List, Dict
'''
        symbols = await parser.parse_file(code, Path("imports.py"))

        imports = [s for s in symbols if s.kind == SymbolKind.IMPORT]
        assert len(imports) >= 1


class TestRegexParser:
    """正则表达式解析器测试"""

    @pytest.fixture
    def parser(self) -> RegexParser:
        return RegexParser()

    @pytest.mark.asyncio
    async def test_parse_typescript(self, parser: RegexParser):
        """测试解析 TypeScript"""
        code = '''
interface User {
  name: string;
  age: number;
}

class UserService {
  getUser(id: string): User {
    return { name: "Test", age: 20 };
  }
}

function greet(name: string): string {
  return `Hello, ${name}`;
}
'''
        symbols = await parser.parse_file(code, Path("test.ts"))

        # 应该解析出 interface, class, function
        kinds = {s.kind for s in symbols}
        assert SymbolKind.INTERFACE in kinds or SymbolKind.CLASS in kinds

    @pytest.mark.asyncio
    async def test_parse_go(self, parser: RegexParser):
        """测试解析 Go"""
        code = '''
package main

type User struct {
    Name string
    Age  int
}

func (u *User) GetName() string {
    return u.Name
}

func main() {
    fmt.Println("Hello")
}
'''
        symbols = await parser.parse_file(code, Path("test.go"))

        # 应该解析出 struct 和 function
        assert len(symbols) > 0


class TestDatabase:
    """数据库测试"""

    @pytest.fixture
    async def db(self) -> CodeSearchDatabase:
        database = CodeSearchDatabase(":memory:")
        await database.initialize()
        yield database
        await database.close()

    @pytest.mark.asyncio
    async def test_store_and_search_symbols(self, db: CodeSearchDatabase):
        """测试存储和搜索符号"""

        from pyagentforge.codesearch.storage.models import Symbol

        symbol = Symbol(
            id="test-1",
            name="test_function",
            kind=SymbolKind.FUNCTION,
            file_path="/test/file.py",
            line_start=1,
            line_end=5,
            column_start=0,
            column_end=20,
            language="python",
            file_hash="abc123",
        )

        await db.store_symbols([symbol])

        # 搜索符号
        results = await db.search_symbols(name="test")
        assert len(results) == 1
        assert results[0].name == "test_function"

    @pytest.mark.asyncio
    async def test_file_hash_operations(self, db: CodeSearchDatabase):
        """测试文件哈希操作"""
        await db.update_file_hash(
            file_path="/test/file.py",
            content_hash="abc123",
            file_size=100,
            modified_time=12345.0,
            symbol_count=5,
        )

        file_hash = await db.get_file_hash("/test/file.py")
        assert file_hash is not None
        assert file_hash.content_hash == "abc123"
        assert file_hash.symbol_count == 5


class TestQueryParser:
    """查询解析器测试"""

    def test_simple_query(self):
        """测试简单查询"""
        parser = QueryParser("hello")
        ast = parser.parse()

        assert ast is not None
        # 应该解析为 NameMatch

    def test_kind_filter(self):
        """测试类型过滤"""
        parser = QueryParser("function:hello")
        ast = parser.parse()

        assert ast is not None

    def test_and_query(self):
        """测试 AND 查询"""
        parser = QueryParser("hello AND world")
        ast = parser.parse()

        assert ast is not None

    def test_or_query(self):
        """测试 OR 查询"""
        parser = QueryParser("hello OR world")
        ast = parser.parse()

        assert ast is not None

    def test_complex_query(self):
        """测试复杂查询"""
        parser = QueryParser("function:execute AND lang:python")
        ast = parser.parse()

        assert ast is not None


class TestCodeSearchConfig:
    """配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = CodeSearchConfig()

        assert config.enabled is True
        assert config.max_results == 100
        assert "*.py" in config.include_patterns

    def test_should_index_file(self):
        """测试文件过滤"""
        config = CodeSearchConfig()

        # 应该索引 Python 文件
        assert config.should_index_file(Path("test.py")) is True
        assert config.should_index_file(Path("src/main.py")) is True

        # 不应该索引 node_modules
        assert config.should_index_file(Path("node_modules/test.js")) is False

    def test_matches_language(self):
        """测试语言匹配"""
        config = CodeSearchConfig()

        assert config.matches_language(Path("test.py")) == "python"
        assert config.matches_language(Path("test.ts")) == "typescript"
        assert config.matches_language(Path("test.go")) == "go"


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"

class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        return a + b
''')

            # 创建工具
            tool = create_codesearch_tool(
                workspace_root=tmpdir,
            )

            # 初始化数据库
            await tool.db.initialize()
            try:
                # 索引目录
                count = await tool.indexer.index_directory(Path(tmpdir))
                assert count >= 1

                # 搜索
                result = await tool.execute("function:hello", path=tmpdir)
                assert "hello" in result

                # 状态
                status = await tool.execute("status")
                assert "Symbols:" in status
            finally:
                await tool.db.close()
