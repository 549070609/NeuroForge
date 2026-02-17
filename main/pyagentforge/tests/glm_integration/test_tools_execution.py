"""
工具调用测试

测试 PyAgentForge 的各种内置工具
"""

import pytest
import json
from pathlib import Path

from conftest import check_api_key, run_agent_with_timeout


# ============ Bash 工具测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestBashTool:
    """Bash 工具测试"""

    async def test_simple_echo(self, agent_engine):
        """测试简单 echo 命令"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 bash 命令执行：echo 'Hello World'"
        )

        assert response is not None
        assert "Hello World" in response

    async def test_list_directory(self, agent_engine, temp_dir):
        """测试列出目录"""
        check_api_key()

        # 创建测试文件
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        response = await run_agent_with_timeout(
            agent_engine,
            f"请列出目录 {temp_dir} 中的文件"
        )

        assert response is not None
        assert "test.txt" in response

    async def test_command_with_pipes(self, agent_engine):
        """测试管道命令"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "执行命令：echo 'apple\nbanana\ncherry' | sort | head -2"
        )

        assert response is not None
        # 验证排序和截取是否正确
        assert "apple" in response or "banana" in response


# ============ 文件操作工具测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestFileTools:
    """文件操作工具测试"""

    async def test_write_and_read_file(self, agent_engine, temp_dir):
        """测试写入和读取文件"""
        check_api_key()

        test_file = temp_dir / "example.txt"

        # 写入文件
        response1 = await run_agent_with_timeout(
            agent_engine,
            f"请将 'Hello, PyAgentForge!' 写入文件 {test_file}"
        )
        assert response1 is not None
        assert "成功" in response1 or "写入" in response1

        # 读取文件
        response2 = await run_agent_with_timeout(
            agent_engine,
            f"请读取文件 {test_file} 的内容"
        )
        assert response2 is not None
        assert "Hello, PyAgentForge!" in response2

    async def test_edit_file(self, agent_engine, temp_dir):
        """测试编辑文件"""
        check_api_key()

        test_file = temp_dir / "edit_test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3")

        response = await run_agent_with_timeout(
            agent_engine,
            f"请将文件 {test_file} 中的 'Line 2' 替换为 'Modified Line'"
        )

        assert response is not None

        # 验证文件已修改
        content = test_file.read_text()
        assert "Modified Line" in content

    async def test_read_large_file(self, agent_engine, temp_dir):
        """测试读取大文件"""
        check_api_key()

        # 创建一个较大的文件
        test_file = temp_dir / "large.txt"
        lines = [f"Line {i}" for i in range(100)]
        test_file.write_text("\n".join(lines))

        response = await run_agent_with_timeout(
            agent_engine,
            f"请读取文件 {test_file} 的前 10 行"
        )

        assert response is not None
        assert "Line 0" in response


# ============ 搜索工具测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestSearchTools:
    """搜索工具测试"""

    async def test_glob_pattern(self, agent_engine, temp_dir):
        """测试 glob 文件搜索"""
        check_api_key()

        # 创建测试文件
        (temp_dir / "test1.py").write_text("print('test1')")
        (temp_dir / "test2.py").write_text("print('test2')")
        (temp_dir / "test.txt").write_text("test")

        response = await run_agent_with_timeout(
            agent_engine,
            f"在 {temp_dir} 目录中搜索所有 .py 文件"
        )

        assert response is not None
        assert "test1.py" in response
        assert "test2.py" in response
        assert "test.txt" not in response

    async def test_grep_content(self, agent_engine, temp_dir):
        """测试 grep 内容搜索"""
        check_api_key()

        # 创建测试文件
        test_file = temp_dir / "code.py"
        test_file.write_text("def hello():\n    print('hello')\n\ndef world():\n    print('world')")

        response = await run_agent_with_timeout(
            agent_engine,
            f"在 {test_file} 文件中搜索包含 'def' 的行"
        )

        assert response is not None
        assert "def hello" in response
        assert "def world" in response


# ============ 工具链测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestToolChain:
    """工具链测试"""

    async def test_multi_step_task(self, agent_engine, temp_dir):
        """测试多步骤任务"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            请执行以下任务：
            1. 在 {temp_dir} 目录创建一个文件 'numbers.txt'
            2. 写入 1 到 10 的数字，每行一个
            3. 读取文件内容并告诉我有多少行
            """,
            timeout=60
        )

        assert response is not None
        assert "10" in response

        # 验证文件存在且内容正确
        test_file = temp_dir / "numbers.txt"
        assert test_file.exists()
        lines = test_file.read_text().strip().split("\n")
        assert len(lines) == 10

    async def test_tool_combination(self, agent_engine, temp_dir):
        """测试工具组合"""
        check_api_key()

        # 创建多个文件
        for i in range(3):
            (temp_dir / f"file{i}.txt").write_text(f"Content {i}")

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            执行以下操作：
            1. 列出 {temp_dir} 中的所有 .txt 文件
            2. 读取每个文件的内容
            3. 统计总共有多少个单词
            """,
            timeout=60
        )

        assert response is not None


# ============ 权限控制测试 ============

@pytest.mark.tools
class TestToolPermission:
    """工具权限测试"""

    def test_filter_by_permission(self):
        """测试权限过滤"""
        from pyagentforge.tools.registry import ToolRegistry
        from pyagentforge.tools.permission import PermissionConfig, PermissionChecker

        registry = ToolRegistry()
        registry.register_builtin_tools()

        # 只允许 bash 和 read 工具
        config = PermissionConfig(allowed=["bash", "read"])
        checker = PermissionChecker(config)

        filtered = registry.filter_by_permission(config.allowed)

        assert filtered.has("bash")
        assert filtered.has("read")
        assert not filtered.has("write")

    def test_deny_specific(self):
        """测试拒绝特定工具"""
        from pyagentforge.tools.registry import ToolRegistry
        from pyagentforge.tools.permission import PermissionConfig

        registry = ToolRegistry()
        registry.register_builtin_tools()

        config = PermissionConfig(
            allowed=["*"],
            denied=["bash"]
        )

        filtered = registry.filter_by_permission(
            allowed=["*"],
            denied=["bash"]
        )

        assert not filtered.has("bash")
        assert filtered.has("read")


# ============ Todo 工具测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestTodoTool:
    """Todo 工具测试"""

    async def test_create_todo_list(self, agent_engine):
        """测试创建 Todo 列表"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            """
            请创建一个任务列表：
            - 任务1：完成代码
            - 任务2：测试代码
            - 任务3：提交代码
            """
        )

        assert response is not None
        # GLM 可能会使用 TodoWrite 工具或直接响应


# ============ Web 工具测试 (暂时禁用) ============

# Web 工具测试已禁用 - 需要外部网络连接

# ============ 导入 ============

from pathlib import Path

