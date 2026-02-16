"""
GLM Integration Test Configuration

配置 GLM Provider 集成测试
"""

import os
import sys
import asyncio
from typing import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "glm-provider"))

from pyagentforge.agents.config import AgentConfig
from pyagentforge.core.engine import AgentEngine
from pyagentforge.tools.registry import ToolRegistry
from glm_provider import GLMProvider


# ============ 配置 ============

GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4-flash")
GLM_BASE_URL = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

# 测试配置
TEST_TIMEOUT = int(os.environ.get("TEST_TIMEOUT", "30"))
TEST_TEMP_DIR = Path(__file__).parent / "temp"


# ============ Fixtures ============

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def glm_provider() -> AsyncGenerator[GLMProvider, None]:
    """创建 GLM Provider"""
    if not GLM_API_KEY:
        pytest.skip("GLM_API_KEY not set")

    provider = GLMProvider(
        api_key=GLM_API_KEY,
        model=GLM_MODEL,
    )
    yield provider


@pytest_asyncio.fixture(scope="function")
async def tool_registry() -> AsyncGenerator[ToolRegistry, None]:
    """创建工具注册表"""
    registry = ToolRegistry()
    registry.register_builtin_tools()
    yield registry


@pytest_asyncio.fixture(scope="function")
async def agent_engine(
    glm_provider: GLMProvider,
    tool_registry: ToolRegistry,
) -> AsyncGenerator[AgentEngine, None]:
    """创建 Agent 引擎"""
    config = AgentConfig(
        system_prompt="你是一个有帮助的 AI 助手，可以执行各种任务。",
    )

    engine = AgentEngine(
        provider=glm_provider,
        tool_registry=tool_registry,
        config=config,
    )

    yield engine


@pytest_asyncio.fixture(scope="function")
async def temp_dir() -> AsyncGenerator[Path, None]:
    """创建临时目录"""
    TEST_TEMP_DIR.mkdir(exist_ok=True)
    yield TEST_TEMP_DIR

    # 清理临时文件
    import shutil
    if TEST_TEMP_DIR.exists():
        shutil.rmtree(TEST_TEMP_DIR, ignore_errors=True)


# ============ 标记 ============

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "basic: 基础功能测试")
    config.addinivalue_line("markers", "tools: 工具调用测试")
    config.addinivalue_line("markers", "streaming: 流式响应测试")
    config.addinivalue_line("markers", "advanced: 高级功能测试")
    config.addinivalue_line("markers", "error: 错误处理测试")
    config.addinivalue_line("markers", "boundary: 边界测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "performance: 性能测试")
    config.addinivalue_line("markers", "slow: 慢速测试")


# ============ 辅助函数 ============

def check_api_key():
    """检查 API Key"""
    if not GLM_API_KEY:
        pytest.skip("GLM_API_KEY environment variable not set")


async def run_agent_with_timeout(engine: AgentEngine, message: str, timeout: int = TEST_TIMEOUT):
    """运行 Agent 并设置超时"""
    try:
        response = await asyncio.wait_for(
            engine.run(message),
            timeout=timeout
        )
        return response
    except asyncio.TimeoutError:
        pytest.fail(f"Agent execution timed out after {timeout}s")
