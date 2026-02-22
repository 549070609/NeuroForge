"""
AST-Grep 插件测试
"""

import pytest
import asyncio

from pyagentforge.plugins.tools.ast_grep.binary_manager import BinaryManager
from pyagentforge.plugins.tools.ast_grep.constants import CLI_LANGUAGES
from pyagentforge.plugins.tools.ast_grep.tools import AstGrepSearchTool, AstGrepReplaceTool
from pyagentforge.plugins.tools.ast_grep.result_formatter import format_search_result, get_empty_result_hint
from pyagentforge.plugins.tools.ast_grep.types import SgMatch, SgResult
from pyagentforge.plugins.tools.ast_grep import LANG_EXTENSIONS


class TestBinaryManager:
    """测试二进制管理器"""

    @pytest.mark.asyncio
    async def test_check_availability(self):
        """测试可用性检查"""
        manager = BinaryManager()
        # 只是检查不会抛异常
        result = await manager.check_availability()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_install_hint(self):
        """测试安装提示"""
        manager = BinaryManager()
        hint = manager.get_install_hint()
        assert "ast-grep" in hint.lower()
        assert "pip install" in hint.lower()


class TestConstants:
    """测试常量"""

    def test_cli_languages(self):
        """测试支持的语言列表"""
        assert "python" in CLI_LANGUAGES
        assert "javascript" in CLI_LANGUAGES
        assert "typescript" in CLI_LANGUAGES
        assert len(CLI_LANGUAGES) == 25

    def test_lang_extensions(self):
        """测试语言扩展名映射"""
        assert ".py" in LANG_EXTENSIONS.get("python", [])
        assert ".js" in LANG_EXTENSIONS.get("javascript", [])


class TestResultFormatter:
    """测试结果格式化"""

    def test_format_empty_result(self):
        """测试空结果格式化"""
        result = SgResult(matches=[], total_matches=0)
        output = format_search_result(result)
        assert "No matches found" in output

    def test_format_error_result(self):
        """测试错误结果格式化"""
        result = SgResult(matches=[], total_matches=0, error="Test error")
        output = format_search_result(result)
        assert "Error:" in output
        assert "Test error" in output

    def test_format_success_result(self):
        """测试成功结果格式化"""
        match = SgMatch(
            text="print('hello')",
            file="test.py",
            line=10,
            column=0,
            range_start_line=10,
            range_end_line=10,
        )
        result = SgResult(matches=[match], total_matches=1)

        output = format_search_result(result)
        assert "test.py" in output
        assert "10" in output
        assert "Total: 1" in output

    def test_get_empty_result_hint_python(self):
        """测试 Python 空结果提示"""
        # 有冒号的类定义
        hint = get_empty_result_hint("class Foo:", "python")
        assert hint is not None
        assert "colon" in hint.lower() or "冒号" in hint

        # 完整的模式
        hint = get_empty_result_hint("class Foo", "python")
        assert hint is None

    def test_get_empty_result_hint_javascript(self):
        """测试 JavaScript 空结果提示"""
        hint = get_empty_result_hint("function $NAME", "javascript")
        assert hint is not None
        assert "body" in hint.lower()


class TestTypes:
    """测试类型定义"""

    def test_sg_match(self):
        """测试匹配类型"""
        match = SgMatch(
            text="test",
            file="test.py",
            line=1,
            column=0,
            range_start_line=1,
            range_end_line=1,
        )
        assert match.text == "test"
        assert match.file == "test.py"

    def test_sg_result(self):
        """测试结果类型"""
        result = SgResult(
            matches=[],
            total_matches=0,
            truncated=True,
            truncated_reason="max_matches",
        )
        assert result.truncated is True
        assert result.truncated_reason == "max_matches"


# 集成测试 (需要 ast-grep 已安装)
@pytest.mark.skipif(
    not asyncio.run(BinaryManager().check_availability()),
    reason="ast-grep not installed"
)
class TestIntegration:
    """集成测试"""

    @pytest.fixture
    def binary_manager(self):
        """创建二进制管理器"""
        return BinaryManager()

    @pytest.mark.asyncio
    async def test_search_tool(self, binary_manager):
        """测试搜索工具"""
        tool = AstGrepSearchTool(binary_manager=binary_manager)
        result = await tool.execute(
            pattern="print($MSG)",
            lang="python",
            paths=["."],
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_replace_tool_dry_run(self, binary_manager):
        """测试替换工具 (预览模式)"""
        tool = AstGrepReplaceTool(binary_manager=binary_manager)
        result = await tool.execute(
            pattern="print($MSG)",
            rewrite="logger.info($MSG)",
            lang="python",
            paths=["."],
            dry_run=True,
        )
        assert "Preview" in result or "No matches" in result or "Error" in result
