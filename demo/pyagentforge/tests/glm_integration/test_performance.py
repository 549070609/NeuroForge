"""
性能测试

测试系统性能和响应时间
"""

import pytest
import time
import asyncio
from pathlib import Path

from conftest import check_api_key, run_agent_with_timeout


# ============ 响应时间测试 ============

@pytest.mark.performance
@pytest.mark.asyncio
class TestResponseTime:
    """响应时间测试"""

    async def test_simple_query_response_time(self, agent_engine):
        """测试简单查询响应时间"""
        check_api_key()

        start_time = time.time()

        response = await run_agent_with_timeout(
            agent_engine,
            "1+1等于多少？"
        )

        elapsed_time = time.time() - start_time

        assert response is not None
        assert elapsed_time < 10  # 应该在 10 秒内完成

        print(f"\n简单查询响应时间: {elapsed_time:.2f}s")

    async def test_complex_query_response_time(self, agent_engine):
        """测试复杂查询响应时间"""
        check_api_key()

        start_time = time.time()

        response = await run_agent_with_timeout(
            agent_engine,
            "请解释量子计算的基本原理，包括量子比特、量子门和量子纠缠",
            timeout=60
        )

        elapsed_time = time.time() - start_time

        assert response is not None
        assert elapsed_time < 60  # 应该在 60 秒内完成

        print(f"\n复杂查询响应时间: {elapsed_time:.2f}s")


# ============ 工具执行性能测试 ============

@pytest.mark.performance
@pytest.mark.asyncio
class TestToolPerformance:
    """工具执行性能测试"""

    async def test_file_read_performance(self, agent_engine, temp_dir):
        """测试文件读取性能"""
        check_api_key()

        # 创建 1MB 文件
        test_file = temp_dir / "perf_test.txt"
        test_file.write_text("A" * (1024 * 1024))

        start_time = time.time()

        response = await run_agent_with_timeout(
            agent_engine,
            f"读取文件 {test_file} 的前 1000 个字符"
        )

        elapsed_time = time.time() - start_time

        assert response is not None
        assert elapsed_time < 15

        print(f"\n1MB 文件读取时间: {elapsed_time:.2f}s")

    async def test_multiple_tool_calls_performance(self, agent_engine, temp_dir):
        """测试多次工具调用性能"""
        check_api_key()

        # 创建 5 个文件
        for i in range(5):
            (temp_dir / f"perf_{i}.txt").write_text(f"Content {i}")

        start_time = time.time()

        response = await run_agent_with_timeout(
            agent_engine,
            f"读取 {temp_dir} 目录中所有 perf_*.txt 文件并总结内容",
            timeout=60
        )

        elapsed_time = time.time() - start_time

        assert response is not None

        print(f"\n5 次文件操作时间: {elapsed_time:.2f}s")


# ============ 吞吐量测试 ============

@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.slow
class TestThroughput:
    """吞吐量测试"""

    async def test_sequential_requests(self):
        """测试顺序请求吞吐量"""
        check_api_key()

        from pyagentforge.agents.config import AgentConfig
        from pyagentforge.core.engine import AgentEngine
        from pyagentforge.tools.registry import ToolRegistry
        from glm_provider import GLMProvider

        num_requests = 10
        start_time = time.time()

        for i in range(num_requests):
            provider = GLMProvider(api_key=GLM_API_KEY, model=GLM_MODEL)
            tools = ToolRegistry()
            tools.register_builtin_tools()

            engine = AgentEngine(
                provider=provider,
                tool_registry=tools,
            )

            response = await engine.run(f"请求 {i+1}")
            assert response is not None

        elapsed_time = time.time() - start_time
        throughput = num_requests / elapsed_time

        print(f"\n顺序吞吐量: {throughput:.2f} req/min")
        assert throughput > 0.5  # 至少 0.5 req/min


# ============ 并发性能测试 ============

@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.slow
class TestConcurrentPerformance:
    """并发性能测试"""

    async def test_concurrent_sessions_performance(self):
        """测试并发会话性能"""
        check_api_key()

        from pyagentforge.agents.config import AgentConfig
        from pyagentforge.core.engine import AgentEngine
        from pyagentforge.tools.registry import ToolRegistry
        from glm_provider import GLMProvider

        async def run_session(session_id: int):
            provider = GLMProvider(api_key=GLM_API_KEY, model=GLM_MODEL)
            tools = ToolRegistry()
            tools.register_builtin_tools()

            engine = AgentEngine(
                provider=provider,
                tool_registry=tools,
            )

            return await engine.run(f"并发会话 {session_id}")

        num_sessions = 5
        start_time = time.time()

        tasks = [run_session(i) for i in range(num_sessions)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed_time = time.time() - start_time

        successful = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successful / num_sessions * 100

        print(f"\n并发 {num_sessions} 个会话:")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  总时间: {elapsed_time:.2f}s")
        print(f"  平均时间: {elapsed_time/num_sessions:.2f}s/会话")

        assert success_rate >= 80  # 至少 80% 成功


# ============ 内存使用测试 ============

@pytest.mark.performance
@pytest.mark.asyncio
@pytest.mark.slow
class TestMemoryUsage:
    """内存使用测试"""

    async def test_session_memory_growth(self, agent_engine):
        """测试会话内存增长"""
        check_api_key()

        import tracemalloc

        tracemalloc.start()

        # 进行多轮对话
        for i in range(10):
            response = await run_agent_with_timeout(
                agent_engine,
                f"这是第 {i+1} 轮对话"
            )
            assert response is not None

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n10 轮对话内存使用:")
        print(f"  当前: {current / 1024 / 1024:.2f} MB")
        print(f"  峰值: {peak / 1024 / 1024:.2f} MB")

        # 峰值不应超过 100MB
        assert peak < 100 * 1024 * 1024


# ============ 导入 ============

from pathlib import Path
from conftest import GLM_API_KEY, GLM_MODEL
