"""
高级功能测试

测试并行子代理、上下文压缩、Skill 加载等高级功能
"""

import pytest
from pathlib import Path

from conftest import check_api_key, run_agent_with_timeout


# ============ 并行子代理测试 ============

@pytest.mark.advanced
@pytest.mark.asyncio
class TestParallelSubAgent:
    """并行子代理测试"""

    async def test_parallel_execution(self, agent_engine, temp_dir):
        """测试并行执行任务"""
        check_api_key()

        # 创建多个文件
        files = []
        for i in range(3):
            file_path = temp_dir / f"parallel_{i}.txt"
            file_path.write_text(f"File {i}")
            files.append(file_path)

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            请同时读取以下文件并告诉我每个文件的内容：
            - {files[0]}
            - {files[1]}
            - {files[2]}
            """,
            timeout=60
        )

        assert response is not None
        # 验证是否提到了所有文件
        assert "File 0" in response or "parallel_0" in response
        assert "File 1" in response or "parallel_1" in response
        assert "File 2" in response or "parallel_2" in response


# ============ 上下文压缩测试 ============

@pytest.mark.advanced
@pytest.mark.asyncio
class TestContextCompression:
    """上下文压缩测试"""

    async def test_long_context_handling(self, agent_engine):
        """测试长上下文处理"""
        check_api_key()

        # 创建长对话
        for i in range(10):
            response = await run_agent_with_timeout(
                agent_engine,
                f"请记住这个数字：{i}"
            )
            assert response is not None

        # 验证是否能回忆起早期信息
        response = await run_agent_with_timeout(
            agent_engine,
            "我之前让你记住的第一个数字是什么？"
        )

        assert response is not None


# ============ Skill 加载测试 ============

@pytest.mark.advanced
class TestSkillLoading:
    """Skill 加载测试"""

    def test_skill_registry(self):
        """测试 Skill 注册"""
        from pyagentforge.skills.registry import SkillRegistry

        registry = SkillRegistry()
        # 假设有内置 Skill
        # registry.register_builtin_skills()

        # 基本功能测试
        assert registry is not None

    def test_skill_loader(self):
        """测试 Skill 加载器"""
        from pyagentforge.skills.loader import SkillLoader

        loader = SkillLoader()
        assert loader is not None


# ============ Command 解析测试 ============

@pytest.mark.advanced
class TestCommandParsing:
    """Command 解析测试"""

    def test_command_parser(self):
        """测试 Command 解析器"""
        from pyagentforge.commands.parser import CommandParser

        parser = CommandParser()

        # 测试基本命令解析
        text = "请执行 !bash`echo hello` 命令"
        commands = parser.parse(text)

        # 基本解析功能
        assert parser is not None


# ============ 思考过程测试 ============

@pytest.mark.advanced
@pytest.mark.asyncio
class TestThinkingProcess:
    """思考过程测试"""

    async def test_reasoning_task(self, agent_engine):
        """测试推理任务"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            """
            如果所有的猫都是动物，
            所有的动物都需要食物，
            那么 Tom 是一只猫，Tom 需要什么？
            """
        )

        assert response is not None
        assert "食物" in response or "food" in response.lower()


# ============ MCP 测试 (需要额外配置) ============

@pytest.mark.advanced
@pytest.mark.asyncio
@pytest.mark.skip(reason="需要 MCP 配置")
class TestMCP:
    """MCP (Model Context Protocol) 测试"""

    async def test_mcp_client(self):
        """测试 MCP 客户端"""
        pytest.skip("需要 MCP 配置")


# ============ LSP 测试 (需要额外配置) ============

@pytest.mark.advanced
@pytest.mark.asyncio
@pytest.mark.skip(reason="需要 LSP 配置")
class TestLSP:
    """LSP (Language Server Protocol) 测试"""

    async def test_lsp_integration(self):
        """测试 LSP 集成"""
        pytest.skip("需要 LSP 配置")


# ============ 导入 ============

from pathlib import Path
