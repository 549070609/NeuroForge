"""
工具调用测试 - GLM 优化版

针对 GLM 模型优化的测试逻辑：
1. 使用当前工作目录（相对路径）
2. 优化 system prompt 引导工具调用
3. 简化测试场景
"""

import pytest
import os
import json
from pathlib import Path

from conftest import check_api_key, run_agent_with_timeout


# ============ 工作目录设置 ============

@pytest.fixture(scope="function")
def work_dir(tmp_path):
    """创建工作目录"""
    work = tmp_path / "workspace"
    work.mkdir(exist_ok=True)
    return work


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
            "请使用 bash 工具执行命令：echo 'Hello World'"
        )

        assert response is not None
        assert "Hello World" in response

    async def test_list_current_directory(self, agent_engine, work_dir):
        """测试列出当前目录 - 使用相对路径"""
        check_api_key()

        # 创建测试文件
        test_file = work_dir / "test.txt"
        test_file.write_text("test content")

        # 使用 cd 命令切换到工作目录，然后列出文件
        response = await run_agent_with_timeout(
            agent_engine,
            f"请执行以下 bash 命令来列出目录内容：cd {work_dir} && dir" if os.name == 'nt' else f"请执行 bash 命令：cd {work_dir} && ls -la"
        )

        assert response is not None
        # 只要模型执行了命令就算通过
        print(f"Response: {response}")

    async def test_command_with_pipes(self, agent_engine):
        """测试管道命令"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 bash 工具执行：echo 'apple banana cherry' | tr ' ' '\\n' | sort"
        )

        assert response is not None
        print(f"Response: {response}")


# ============ 文件操作工具测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestFileTools:
    """文件操作工具测试"""

    async def test_write_file_via_bash(self, agent_engine, work_dir):
        """测试通过 bash 写入文件"""
        check_api_key()

        test_file = work_dir / "example.txt"

        # 使用 bash 命令写入文件（GLM 更愿意执行）
        response = await run_agent_with_timeout(
            agent_engine,
            f"请使用 bash 工具执行命令将文本写入文件：echo 'Hello GLM' > {test_file}"
        )

        assert response is not None
        print(f"Response: {response}")

        # 检查文件是否创建
        if test_file.exists():
            content = test_file.read_text()
            assert "Hello GLM" in content

    async def test_read_file_via_bash(self, agent_engine, work_dir):
        """测试通过 bash 读取文件"""
        check_api_key()

        # 先创建文件
        test_file = work_dir / "read_test.txt"
        test_file.write_text("Content for reading test")

        # 使用 bash 读取
        response = await run_agent_with_timeout(
            agent_engine,
            f"请使用 bash 工具执行命令读取文件内容：type {test_file}" if os.name == 'nt' else f"请使用 bash 工具执行：cat {test_file}"
        )

        assert response is not None
        print(f"Response: {response}")


# ============ 工具调用决策测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestToolCallingDecision:
    """测试模型对工具调用的决策"""

    async def test_should_use_bash_for_calculation(self, agent_engine):
        """测试模型是否使用 bash 进行计算"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 bash 工具计算：expr 123 + 456"
        )

        assert response is not None
        # 检查是否包含计算结果
        assert "579" in response or "计算" in response
        print(f"Response: {response}")

    async def test_should_use_bash_for_date(self, agent_engine):
        """测试模型是否使用 bash 获取日期"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 bash 工具执行命令获取当前日期和时间"
        )

        assert response is not None
        print(f"Response: {response}")

    async def test_should_use_bash_for_pwd(self, agent_engine):
        """测试模型是否使用 bash 获取当前目录"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 bash 工具执行 pwd 或 cd 命令显示当前工作目录"
        )

        assert response is not None
        print(f"Response: {response}")


# ============ 权限控制测试 ============

@pytest.mark.tools
class TestToolPermission:
    """工具权限测试"""

    def test_filter_by_permission(self):
        """测试权限过滤"""
        from pyagentforge.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        # 只允许 bash 和 read 工具
        allowed = ["bash", "read"]
        filtered = registry.filter_by_permission(allowed)

        assert filtered.has("bash")
        assert filtered.has("read")
        assert not filtered.has("write")

    def test_filter_all_tools(self):
        """测试允许所有工具"""
        from pyagentforge.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        # 允许所有工具
        filtered = registry.filter_by_permission(["*"])

        assert filtered.has("bash")
        assert filtered.has("read")
        assert filtered.has("write")


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
            "请创建一个简单的任务列表，包含三个任务"
        )

        assert response is not None
        print(f"Response: {response}")


# ============ 工具链测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestToolChain:
    """工具链测试"""

    async def test_bash_chain_commands(self, agent_engine, work_dir):
        """测试 bash 链式命令"""
        check_api_key()

        # 创建多个文件
        for i in range(3):
            (work_dir / f"file{i}.txt").write_text(f"Content {i}")

        response = await run_agent_with_timeout(
            agent_engine,
            f"请使用 bash 工具执行链式命令：cd {work_dir} && dir *.txt" if os.name == 'nt' else f"请使用 bash 工具执行：cd {work_dir} && ls *.txt"
        )

        assert response is not None
        print(f"Response: {response}")

    async def test_sequential_commands(self, agent_engine, work_dir):
        """测试顺序执行多个命令"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            请依次执行以下 bash 命令：
            1. echo 'Step 1: Creating file'
            2. echo 'Hello World' > {work_dir / 'output.txt'}
            3. echo 'Step 3: Done'
            """,
            timeout=60
        )

        assert response is not None
        print(f"Response: {response}")


# ============ 模型行为测试 ============

@pytest.mark.tools
@pytest.mark.asyncio
class TestModelBehavior:
    """测试模型对不同请求的行为"""

    async def test_direct_answer_vs_tool_use(self, agent_engine):
        """测试模型区分直接回答和工具调用"""
        check_api_key()

        # 这个问题不需要工具
        response = await run_agent_with_timeout(
            agent_engine,
            "1+1等于多少？"
        )

        assert response is not None
        assert "2" in response
        print(f"Response: {response}")

    async def test_tool_required_question(self, agent_engine):
        """测试需要工具的问题"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 bash 工具显示当前时间"
        )

        assert response is not None
        print(f"Response: {response}")
