"""
边界测试

测试边界条件和极端情况
"""

import pytest
from pathlib import Path

from conftest import check_api_key, run_agent_with_timeout


# ============ 长上下文测试 ============

@pytest.mark.boundary
@pytest.mark.asyncio
@pytest.mark.slow
class TestLongContext:
    """长上下文测试"""

    async def test_many_turns_conversation(self, agent_engine):
        """测试多轮对话（20轮）"""
        check_api_key()

        # 进行 20 轮对话
        for i in range(20):
            response = await run_agent_with_timeout(
                agent_engine,
                f"这是第 {i+1} 轮对话，请确认。"
            )
            assert response is not None

        # 验证最后一轮
        assert "21" not in response  # 最后一轮是第 20 轮

    async def test_large_context_content(self, agent_engine):
        """测试大上下文内容"""
        check_api_key()

        # 创建一个长消息
        long_text = "这是一段测试文本。 " * 100  # ~1000 字符

        response = await run_agent_with_timeout(
            agent_engine,
            f"请记住这段文本：{long_text}",
            timeout=60
        )

        assert response is not None


# ============ 大文件测试 ============

@pytest.mark.boundary
@pytest.mark.asyncio
@pytest.mark.slow
class TestLargeFiles:
    """大文件测试"""

    async def test_read_large_file(self, agent_engine, temp_dir):
        """测试读取大文件（10MB）"""
        check_api_key()

        # 创建 10MB 文件
        large_file = temp_dir / "large.txt"
        size_mb = 10
        chunk = "A" * 1024 * 1024  # 1MB

        with open(large_file, "w") as f:
            for _ in range(size_mb):
                f.write(chunk)

        response = await run_agent_with_timeout(
            agent_engine,
            f"请读取文件 {large_file} 的前 100 个字符",
            timeout=60
        )

        assert response is not None

    async def test_many_files_operations(self, agent_engine, temp_dir):
        """测试多文件操作（100个文件）"""
        check_api_key()

        # 创建 100 个文件
        for i in range(100):
            file_path = temp_dir / f"file_{i}.txt"
            file_path.write_text(f"Content {i}")

        response = await run_agent_with_timeout(
            agent_engine,
            f"请统计 {temp_dir} 目录中有多少个 .txt 文件",
            timeout=60
        )

        assert response is not None
        assert "100" in response


# ============ 工具调用次数测试 ============

@pytest.mark.boundary
@pytest.mark.asyncio
@pytest.mark.slow
class TestManyToolCalls:
    """大量工具调用测试"""

    async def test_sequential_tool_calls(self, agent_engine, temp_dir):
        """测试连续工具调用（10次）"""
        check_api_key()

        # 请求执行多个工具调用
        tasks = []
        for i in range(10):
            tasks.append(f"{i+1}. 创建文件 {temp_dir}/seq_{i}.txt 并写入内容 'File {i}'")

        response = await run_agent_with_timeout(
            agent_engine,
            "请按顺序执行以下任务：\n" + "\n".join(tasks),
            timeout=120
        )

        assert response is not None

        # 验证文件创建
        created_count = sum(1 for i in range(10) if (temp_dir / f"seq_{i}.txt").exists())
        assert created_count >= 8  # 允许部分失败


# ============ 并发会话测试 ============

@pytest.mark.boundary
@pytest.mark.asyncio
@pytest.mark.slow
class TestConcurrentSessions:
    """并发会话测试"""

    async def test_multiple_sessions(self):
        """测试多个并发会话"""
        check_api_key()

        from pyagentforge.agents.config import AgentConfig
        from pyagentforge.core.engine import AgentEngine
        from pyagentforge.tools.registry import ToolRegistry
        from glm_provider import GLMProvider
        import asyncio

        # 创建 5 个并发会话
        async def create_and_run_session(session_id: int):
            provider = GLMProvider(
                api_key=GLM_API_KEY,
                model=GLM_MODEL,
            )
            tools = ToolRegistry()
            tools.register_builtin_tools()

            config = AgentConfig(
                system_prompt=f"你是会话 {session_id} 的助手"
            )

            engine = AgentEngine(
                provider=provider,
                tool_registry=tools,
                config=config,
            )

            return await engine.run(f"会话 {session_id}：你好")

        # 并发运行
        tasks = [create_and_run_session(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 验证至少 80% 成功
        successful = sum(1 for r in results if not isinstance(r, Exception))
        assert successful >= 4


# ============ Token 限制测试 ============

@pytest.mark.boundary
@pytest.mark.asyncio
class TestTokenLimits:
    """Token 限制测试"""

    async def test_max_tokens_limit(self, glm_provider, tool_registry):
        """测试最大 Token 限制"""
        check_api_key()

        from pyagentforge.agents.config import AgentConfig
        from pyagentforge.core.engine import AgentEngine

        # 设置较小的 max_tokens
        config = AgentConfig(
            system_prompt="你是一个助手",
            max_tokens=100
        )

        # 创建 Provider 也设置 max_tokens
        glm_provider.max_tokens = 100

        engine = AgentEngine(
            provider=glm_provider,
            tool_registry=tool_registry,
            config=config,
        )

        response = await run_agent_with_timeout(
            engine,
            "请详细介绍一下 Python 编程语言的历史、特性和应用场景"
        )

        assert response is not None
        # 响应应该被截断或简化
        assert len(response) < 1000  # 粗略估计


# ============ 特殊输入测试 ============

@pytest.mark.boundary
@pytest.mark.asyncio
class TestSpecialInputs:
    """特殊输入测试"""

    async def test_unicode_input(self, agent_engine):
        """测试 Unicode 输入"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "特殊字符：😀🎉🔥 αβγδ 日本語 한국어"
        )

        assert response is not None

    async def test_code_blocks(self, agent_engine):
        """测试代码块输入"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            """
            分析这段代码：
            ```python
            def hello():
                print("Hello, World!")
            ```
            """
        )

        assert response is not None
        assert "python" in response.lower() or "代码" in response or "function" in response.lower()

    async def test_markdown_formatting(self, agent_engine):
        """测试 Markdown 格式"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            """
            请用 Markdown 格式回复：
            - 标题
            - 列表
            - **粗体**
            - *斜体*
            """
        )

        assert response is not None


# ============ 导入 ============

from pathlib import Path
from conftest import GLM_API_KEY, GLM_MODEL
