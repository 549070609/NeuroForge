"""
错误处理测试

测试各种错误场景和异常处理
"""

import pytest
from pathlib import Path

from conftest import check_api_key, run_agent_with_timeout


# ============ 无效工具测试 ============

@pytest.mark.error
@pytest.mark.asyncio
class TestInvalidTool:
    """无效工具测试"""

    async def test_nonexistent_tool_request(self, agent_engine):
        """测试请求不存在的工具"""
        check_api_key()

        # GLM 模型可能会拒绝执行或提供替代方案
        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 nonexistent_tool_xyz 执行任务"
        )

        # 应该有响应，即使是错误提示或替代方案
        assert response is not None

    async def test_invalid_tool_parameters(self, agent_engine):
        """测试无效的工具参数"""
        check_api_key()

        # 提供不完整的参数
        response = await run_agent_with_timeout(
            agent_engine,
            "请使用 bash 工具，但不提供 command 参数"
        )

        # 模型应该处理这种情况
        assert response is not None


# ============ 文件操作错误测试 ============

@pytest.mark.error
@pytest.mark.asyncio
class TestFileOperationErrors:
    """文件操作错误测试"""

    async def test_read_nonexistent_file(self, agent_engine):
        """测试读取不存在的文件"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请读取文件 /nonexistent/path/to/file.txt"
        )

        assert response is not None
        # 应该包含错误提示
        assert "不存在" in response or "找不到" in response or "Error" in response or "不存在" in response

    async def test_write_to_invalid_path(self, agent_engine):
        """测试写入无效路径"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请将内容写入 /root/protected/file.txt"
        )

        assert response is not None
        # 应该包含权限或路径错误提示
        assert "权限" in response or "错误" in response or "Error" in response or "失败" in response


# ============ 命令执行错误测试 ============

@pytest.mark.error
@pytest.mark.asyncio
class TestCommandErrors:
    """命令执行错误测试"""

    async def test_invalid_command(self, agent_engine):
        """测试无效命令"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请执行命令：nonexistent_command_12345"
        )

        assert response is not None
        # 应该包含错误提示
        assert "not found" in response.lower() or "找不到" in response or "错误" in response or "Error" in response

    async def test_command_with_syntax_error(self, agent_engine):
        """测试语法错误的命令"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请执行命令：echo 'unclosed string"
        )

        assert response is not None


# ============ 输入验证测试 ============

@pytest.mark.error
@pytest.mark.asyncio
class TestInputValidation:
    """输入验证测试"""

    async def test_empty_message(self, agent_engine):
        """测试空消息"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            ""
        )

        # 应该有响应或提示
        assert response is not None

    async def test_very_long_message(self, agent_engine):
        """测试超长消息"""
        check_api_key()

        long_message = "测试 " * 1000  # 2000 字符

        response = await run_agent_with_timeout(
            agent_engine,
            long_message,
            timeout=60
        )

        # 应该能处理或拒绝
        assert response is not None

    async def test_special_characters(self, agent_engine):
        """测试特殊字符"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "特殊字符测试：<>&\"'{}[]\\n\\t"
        )

        assert response is not None


# ============ 超时测试 ============

@pytest.mark.error
@pytest.mark.asyncio
class TestTimeout:
    """超时测试"""

    @pytest.mark.slow
    async def test_long_running_task(self, agent_engine):
        """测试长时间运行任务"""
        check_api_key()

        # 请求一个可能很慢的任务
        response = await run_agent_with_timeout(
            agent_engine,
            "请生成一个包含 1000 行的 Python 代码文件",
            timeout=60
        )

        # 应该能完成或超时
        assert response is not None


# ============ 并发冲突测试 ============

@pytest.mark.error
@pytest.mark.asyncio
class TestConcurrencyIssues:
    """并发冲突测试"""

    async def test_concurrent_file_access(self, agent_engine, temp_dir):
        """测试并发文件访问"""
        check_api_key()

        test_file = temp_dir / "concurrent.txt"

        # 请求同时读写同一文件
        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            同时执行：
            1. 将 "Hello" 写入 {test_file}
            2. 读取 {test_file}
            """,
            timeout=60
        )

        assert response is not None


# ============ 模型错误测试 ============

@pytest.mark.error
@pytest.mark.asyncio
class TestModelErrors:
    """模型错误测试"""

    async def test_api_error_handling(self):
        """测试 API 错误处理"""
        from pyagentforge.agents.config import AgentConfig
        from pyagentforge.core.engine import AgentEngine
        from pyagentforge.tools.registry import ToolRegistry
        from glm_provider import GLMProvider

        # 使用无效 API Key
        with pytest.raises(ValueError):
            provider = GLMProvider(
                api_key="invalid_key_12345",
                model="glm-4-flash"
            )


# ============ 上下文错误测试 ============

@pytest.mark.error
class TestContextErrors:
    """上下文错误测试"""

    def test_invalid_message_format(self):
        """测试无效消息格式"""
        from pyagentforge.core.context import ContextManager

        ctx = ContextManager()

        # 添加正常消息
        ctx.add_user_message("Test")

        # 尝试添加无效消息
        # 这里主要测试系统不会崩溃
        assert len(ctx) == 1


# ============ 导入 ============

from pathlib import Path
