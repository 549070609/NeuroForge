"""
测试配置
"""

import asyncio
from typing import Generator

import pytest

from pyagentforge.config.settings import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """测试配置"""
    return Settings(
        anthropic_api_key="test-key",
        openai_api_key="test-key",
        debug=True,
    )
