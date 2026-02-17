"""
PyAgentForge 压力测试套件

包括：并发测试、长时间运行、大数据量、极限条件等
"""

import pytest
import asyncio
import time
import tracemalloc
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from conftest import check_api_key, GLM_API_KEY, GLM_MODEL
from pyagentforge.agents.config import AgentConfig
from pyagentforge.core.engine import AgentEngine
from pyagentforge.tools.registry import ToolRegistry
from glm_provider import GLMProvider


# ============ 并发压力测试 ============

@pytest.mark.stress
@pytest.mark.asyncio
class TestConcurrencyStress:
    """并发压力测试"""

    async def test_concurrent_5_sessions(self):
        """测试 5 个并发会话"""
        check_api_key()

        async def create_session(session_id: int) -> Dict:
            """创建并运行单个会话"""
            try:
                provider = GLMProvider(api_key=GLM_API_KEY, model=GLM_MODEL)
                tools = ToolRegistry()
                tools.register_builtin_tools()

                engine = AgentEngine(
                    provider=provider,
                    tool_registry=tools,
                    config=AgentConfig(system_prompt=f"你是会话 {session_id} 的助手")
                )

                start_time = time.time()
                response = await engine.run(f"会话 {session_id}：你好，请简短回复")
                elapsed_time = time.time() - start_time

                return {
                    "session_id": session_id,
                    "success": True,
                    "elapsed_time": elapsed_time,
                    "response_length": len(response)
                }
            except Exception as e:
                return {
                    "session_id": session_id,
                    "success": False,
                    "error": str(e)
                }

        print("\n[压力测试] 启动 5 个并发会话...")
        start_time = time.time()

        # 并发运行 5 个会话
        tasks = [create_session(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # 统计结果
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        success_rate = len(successful) / len(results) * 100

        # 打印报告
        print(f"\n[并发测试结果]")
        print(f"  总会话数: {len(results)}")
        print(f"  成功: {len(successful)}")
        print(f"  失败: {len(failed)}")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  总耗时: {total_time:.2f}s")
        if successful:
            avg_time = sum(r["elapsed_time"] for r in successful) / len(successful)
            print(f"  平均响应时间: {avg_time:.2f}s")

        # 断言
        assert success_rate >= 80, f"成功率 {success_rate:.1f}% 低于 80%"
        assert total_time < 120, f"总耗时 {total_time:.2f}s 超过 120s"

    async def test_concurrent_10_sessions(self):
        """测试 10 个并发会话（极限）"""
        check_api_key()

        async def quick_session(session_id: int) -> Dict:
            """快速会话"""
            try:
                provider = GLMProvider(api_key=GLM_API_KEY, model=GLM_MODEL)
                tools = ToolRegistry()

                engine = AgentEngine(
                    provider=provider,
                    tool_registry=tools,
                )

                start_time = time.time()
                response = await engine.run(f"测试 {session_id}")
                elapsed_time = time.time() - start_time

                return {
                    "session_id": session_id,
                    "success": True,
                    "elapsed_time": elapsed_time
                }
            except Exception as e:
                return {
                    "session_id": session_id,
                    "success": False,
                    "error": str(e)
                }

        print("\n[极限测试] 启动 10 个并发会话...")
        start_time = time.time()

        tasks = [quick_session(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        successful = [r for r in results if r["success"]]
        success_rate = len(successful) / len(results) * 100

        print(f"\n[极限并发测试结果]")
        print(f"  成功率: {success_rate:.1f}% ({len(successful)}/10)")
        print(f"  总耗时: {total_time:.2f}s")

        # 宽松的断言（10并发可能失败）
        assert success_rate >= 60, f"成功率过低: {success_rate:.1f}%"


# ============ 长时间运行测试 ============

@pytest.mark.stress
@pytest.mark.asyncio
@pytest.mark.slow
class TestLongRunningStress:
    """长时间运行压力测试"""

    async def test_20_turns_conversation(self, agent_engine):
        """测试 20 轮连续对话"""
        check_api_key()

        print("\n[长时间测试] 启动 20 轮连续对话...")

        tracemalloc.start()
        start_time = time.time()

        messages = [f"第 {i+1} 轮：请简短回复" for i in range(20)]
        results = []

        for i, msg in enumerate(messages):
            try:
                response = await agent_engine.run(msg)
                results.append({
                    "turn": i + 1,
                    "success": True,
                    "response_length": len(response)
                })
                print(f"  第 {i+1}/20 轮完成")
            except Exception as e:
                results.append({
                    "turn": i + 1,
                    "success": False,
                    "error": str(e)
                })

        elapsed_time = time.time() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 统计
        successful = [r for r in results if r["success"]]
        success_rate = len(successful) / len(results) * 100

        print(f"\n[长时间测试结果]")
        print(f"  总轮数: {len(results)}")
        print(f"  成功: {len(successful)}")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  总耗时: {elapsed_time:.2f}s")
        print(f"  平均每轮: {elapsed_time/len(results):.2f}s")
        print(f"  峰值内存: {peak_mem / 1024 / 1024:.2f} MB")

        assert success_rate >= 90, f"成功率 {success_rate:.1f}% 低于 90%"
        assert peak_mem < 100 * 1024 * 1024, f"内存使用过高: {peak_mem / 1024 / 1024:.2f} MB"

    async def test_memory_leak_detection(self, agent_engine):
        """内存泄漏检测"""
        check_api_key()

        print("\n[内存泄漏检测] 执行 10 轮对话...")

        tracemalloc.start()

        # 初始内存
        _ = await agent_engine.run("初始化")
        baseline_mem = tracemalloc.get_traced_memory()[0]

        # 执行 10 轮
        for i in range(10):
            _ = await agent_engine.run(f"测试 {i+1}")

        # 最终内存
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # 内存增长
        mem_growth = current_mem - baseline_mem
        growth_mb = mem_growth / 1024 / 1024

        print(f"\n[内存泄漏检测结果]")
        print(f"  基准内存: {baseline_mem / 1024 / 1024:.2f} MB")
        print(f"  最终内存: {current_mem / 1024 / 1024:.2f} MB")
        print(f"  内存增长: {growth_mb:.2f} MB")
        print(f"  峰值内存: {peak_mem / 1024 / 1024:.2f} MB")

        # 断言：内存增长不应超过 50MB
        assert growth_mb < 50, f"潜在内存泄漏: 增长 {growth_mb:.2f} MB"


# ============ 大数据量测试 ============

@pytest.mark.stress
@pytest.mark.asyncio
@pytest.mark.slow
class TestDataVolumeStress:
    """大数据量压力测试"""

    async def test_large_context_accumulation(self, agent_engine):
        """测试大量上下文累积"""
        check_api_key()

        print("\n[大数据量测试] 累积大量上下文...")

        # 创建长文本
        long_text = "这是一段测试文本。" * 100  # ~1000 字符

        start_time = time.time()

        # 添加 10 次长文本
        for i in range(10):
            response = await agent_engine.run(f"请记住：{long_text}（第{i+1}段）")
            print(f"  添加第 {i+1}/10 段长文本")

        # 测试是否能记住
        response = await agent_engine.run("我刚才让你记住的第1段内容是什么？")

        elapsed_time = time.time() - start_time
        context_length = len(agent_engine.context)

        print(f"\n[大数据量测试结果]")
        print(f"  上下文消息数: {context_length}")
        print(f"  总耗时: {elapsed_time:.2f}s")
        print(f"  能否回忆: {'是' if '测试文本' in response else '否'}")

        assert context_length >= 20, "上下文累积不足"

    async def test_rapid_requests(self):
        """测试快速连续请求"""
        check_api_key()

        print("\n[快速请求测试] 发送 10 个快速连续请求...")

        provider = GLMProvider(api_key=GLM_API_KEY, model=GLM_MODEL)
        tools = ToolRegistry()
        tools.register_builtin_tools()

        engine = AgentEngine(
            provider=provider,
            tool_registry=tools,
        )

        start_time = time.time()
        results = []

        for i in range(10):
            try:
                response = await engine.run(f"快速测试 {i+1}")
                results.append({"success": True, "length": len(response)})
            except Exception as e:
                results.append({"success": False, "error": str(e)})

            print(f"  完成 {i+1}/10")

        elapsed_time = time.time() - start_time

        successful = [r for r in results if r["success"]]
        success_rate = len(successful) / len(results) * 100
        throughput = len(successful) / elapsed_time * 60  # req/min

        print(f"\n[快速请求测试结果]")
        print(f"  成功率: {success_rate:.1f}%")
        print(f"  总耗时: {elapsed_time:.2f}s")
        print(f"  吞吐量: {throughput:.2f} req/min")

        assert success_rate >= 80, f"成功率过低: {success_rate:.1f}%"


# ============ 极限条件测试 ============

@pytest.mark.stress
@pytest.mark.asyncio
class TestExtremeConditions:
    """极限条件测试"""

    async def test_max_token_limit(self, glm_provider, tool_registry):
        """测试 Token 限制"""
        check_api_key()

        from pyagentforge.core.engine import AgentEngine

        # 设置很小的 max_tokens
        config = AgentConfig(
            system_prompt="你是一个助手",
            max_tokens=50
        )
        glm_provider.max_tokens = 50

        engine = AgentEngine(
            provider=glm_provider,
            tool_registry=tool_registry,
            config=config,
        )

        print("\n[Token 限制测试] 请求长回复...")

        # 请求长回复
        response = await engine.run(
            "请详细介绍一下 Python 编程语言的历史、特性和应用场景，至少 500 字"
        )

        print(f"\n[Token 限制测试结果]")
        print(f"  响应长度: {len(response)} 字符")
        print(f"  是否被截断: {'是' if len(response) < 200 else '否'}")

        # 响应应该被截断
        assert len(response) < 500, "Token 限制未生效"

    async def test_empty_and_special_input(self, agent_engine):
        """测试空输入和特殊输入"""
        check_api_key()

        print("\n[特殊输入测试] 测试各种边界输入...")

        test_cases = [
            ("空字符串", ""),
            ("空格", "   "),
            ("单个字符", "a"),
            ("特殊字符", "<>&\"'{}[]\\n\\t"),
            ("Unicode", "😀🎉🔥 αβγδ"),
            ("超长空格", " " * 1000),
        ]

        results = []

        for name, input_text in test_cases:
            try:
                response = await agent_engine.run(input_text)
                results.append({
                    "name": name,
                    "success": True,
                    "has_response": len(response) > 0
                })
                print(f"  {name}: 成功")
            except Exception as e:
                results.append({
                    "name": name,
                    "success": False,
                    "error": str(e)
                })
                print(f"  {name}: 失败 - {str(e)[:50]}")

        successful = [r for r in results if r["success"]]
        success_rate = len(successful) / len(results) * 100

        print(f"\n[特殊输入测试结果]")
        print(f"  成功率: {success_rate:.1f}% ({len(successful)}/{len(results)})")

        # 至少 80% 应该能处理
        assert success_rate >= 80, f"特殊输入处理能力不足: {success_rate:.1f}%"


# ============ 性能基准测试 ============

@pytest.mark.stress
@pytest.mark.asyncio
class TestPerformanceBenchmark:
    """性能基准测试"""

    async def test_response_time_benchmark(self, agent_engine):
        """响应时间基准测试"""
        check_api_key()

        print("\n[性能基准] 测试响应时间...")

        test_queries = [
            "你好",
            "1+1等于多少？",
            "Python 是什么？",
            "请写一首诗",
            "请解释机器学习",
        ]

        results = []

        for query in test_queries:
            start_time = time.time()
            response = await agent_engine.run(query)
            elapsed_time = time.time() - start_time

            results.append({
                "query": query,
                "time": elapsed_time,
                "length": len(response)
            })
            print(f"  '{query}': {elapsed_time:.2f}s")

        avg_time = sum(r["time"] for r in results) / len(results)
        max_time = max(r["time"] for r in results)
        min_time = min(r["time"] for r in results)

        print(f"\n[性能基准结果]")
        print(f"  平均响应时间: {avg_time:.2f}s")
        print(f"  最快: {min_time:.2f}s")
        print(f"  最慢: {max_time:.2f}s")

        assert avg_time < 10, f"平均响应时间过长: {avg_time:.2f}s"

    async def test_throughput_benchmark(self):
        """吞吐量基准测试"""
        check_api_key()

        print("\n[吞吐量基准] 测试 1 分钟内的处理能力...")

        provider = GLMProvider(api_key=GLM_API_KEY, model=GLM_MODEL)
        tools = ToolRegistry()

        engine = AgentEngine(
            provider=provider,
            tool_registry=tools,
        )

        # 在 60 秒内尽可能多地处理请求
        start_time = time.time()
        count = 0
        target_time = 60  # 60 秒

        while time.time() - start_time < target_time:
            try:
                _ = await engine.run(f"测试 {count+1}")
                count += 1
                print(f"  已完成 {count} 个请求...")
            except Exception:
                break

        elapsed_time = time.time() - start_time
        throughput = count / elapsed_time * 60  # req/min

        print(f"\n[吞吐量基准结果]")
        print(f"  完成请求数: {count}")
        print(f"  实际用时: {elapsed_time:.2f}s")
        print(f"  吞吐量: {throughput:.2f} req/min")

        # 至少应该能处理 5 req/min
        assert throughput >= 5, f"吞吐量过低: {throughput:.2f} req/min"
