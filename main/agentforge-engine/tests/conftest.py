"""
PyAgentForge Test Configuration

Shared fixtures and configuration for all test modules.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyagentforge import BackgroundManager, ConcurrencyConfig, ConcurrencyManager
from pyagentforge.config.settings import Settings
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentEngine
from pyagentforge.kernel.executor import ToolExecutor
from pyagentforge.kernel.message import Message, ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.tools.registry import ToolRegistry


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Test Settings
# ============================================================================

@pytest.fixture
def test_settings() -> Settings:
    """Test configuration with mock API keys."""
    return Settings(
        anthropic_api_key="test-anthropic-key",
        openai_api_key="test-openai-key",
        google_api_key="test-google-key",
        debug=True,
    )


# ============================================================================
# Mock Provider
# ============================================================================

class MockProvider:
    """Configurable mock provider for testing."""

    def __init__(self, responses: list[ProviderResponse] | None = None):
        self.responses = responses or []
        self.call_count = 0
        self.call_history: list[dict[str, Any]] = []

    async def create_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> ProviderResponse:
        """Return pre-configured responses."""
        self.call_history.append({
            "system": system,
            "messages": messages,
            "tools": tools,
            "kwargs": kwargs
        })

        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
        else:
            # Default response
            response = ProviderResponse(
                content=[TextBlock(text="Default mock response")],
                stop_reason="end_turn"
            )

        self.call_count += 1
        return response

    async def count_tokens(self, messages: list[dict]) -> int:
        """Simple token counting for tests."""
        return sum(len(str(m)) // 4 for m in messages)


@pytest.fixture
def mock_provider():
    """Create a basic mock provider."""
    return MockProvider()


@pytest.fixture
def mock_provider_with_tool_calls():
    """Create a mock provider that returns tool calls."""
    return MockProvider(responses=[
        ProviderResponse(
            content=[
                TextBlock(text="I'll help you with that."),
                ToolUseBlock(
                    id="tool_1",
                    name="read",
                    input={"file_path": "/tmp/test.txt"}
                )
            ],
            stop_reason="tool_use"
        ),
        ProviderResponse(
            content=[TextBlock(text="Done!")],
            stop_reason="end_turn"
        )
    ])


# ============================================================================
# Tool Registry
# ============================================================================

@pytest.fixture
def tool_registry():
    """Create a tool registry with builtin tools."""
    registry = ToolRegistry()
    registry.register_builtin_tools()
    return registry


@pytest.fixture
def empty_tool_registry():
    """Create an empty tool registry."""
    return ToolRegistry()


# ============================================================================
# Context Manager
# ============================================================================

@pytest.fixture
def context_manager():
    """Create a context manager with default settings."""
    return ContextManager(max_messages=100, max_tokens=4000)


@pytest.fixture
def small_context_manager():
    """Create a context manager with small limits for testing truncation."""
    return ContextManager(max_messages=5, max_tokens=100)


# ============================================================================
# Tool Executor
# ============================================================================

@pytest.fixture
def tool_executor(tool_registry):
    """Create a tool executor with default settings."""
    return ToolExecutor(tool_registry=tool_registry, timeout=30)


# ============================================================================
# Agent Engine
# ============================================================================

@pytest.fixture
async def agent_engine(mock_provider, tool_registry):
    """Create an agent engine for testing."""
    engine = AgentEngine(
        provider=mock_provider,
        tool_registry=tool_registry,
        max_iterations=10
    )
    return engine


@pytest.fixture
async def agent_engine_with_tools(mock_provider_with_tool_calls, tool_registry):
    """Create an agent engine with tool-calling provider."""
    engine = AgentEngine(
        provider=mock_provider_with_tool_calls,
        tool_registry=tool_registry,
        max_iterations=10
    )
    return engine


# ============================================================================
# Concurrency Manager
# ============================================================================

@pytest.fixture
def concurrency_config():
    """Create default concurrency configuration."""
    return ConcurrencyConfig(
        max_global=10,
        max_per_model=5,
        max_per_provider=8,
        queue_timeout=30.0,
    )


@pytest.fixture
async def concurrency_manager(concurrency_config):
    """Create a concurrency manager."""
    manager = ConcurrencyManager(config=concurrency_config)
    yield manager
    manager.clear()


# ============================================================================
# Background Manager
# ============================================================================

@pytest.fixture
async def background_manager(concurrency_manager):
    """Create a background manager for testing."""
    manager = BackgroundManager(
        concurrency_config=concurrency_manager.config,
        notification_delay=0.1
    )
    await manager.start()
    yield manager
    await manager.stop()


# ============================================================================
# File System
# ============================================================================

@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with test files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create test files
    (workspace / "test.py").write_text("print('hello world')")
    (workspace / "config.yaml").write_text("key: value\n")
    (workspace / "README.md").write_text("# Test Project\n")

    # Create subdirectory
    subdir = workspace / "src"
    subdir.mkdir()
    (subdir / "main.py").write_text("def main(): pass\n")

    return workspace


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file for testing."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Test content\nLine 2\nLine 3\n")
    return file_path


# ============================================================================
# Messages
# ============================================================================

@pytest.fixture
def sample_user_message():
    """Create a sample user message."""
    return Message(role="user", content="Hello, how are you?")


@pytest.fixture
def sample_assistant_message():
    """Create a sample assistant message."""
    return Message(role="assistant", content="I'm doing well, thank you!")


@pytest.fixture
def sample_tool_result():
    """Create a sample tool result message."""
    return Message(
        role="user",
        content=[{
            "type": "tool_result",
            "tool_use_id": "tool_123",
            "content": "File read successfully"
        }]
    )


# ============================================================================
# Assertions and Helpers
# ============================================================================

class TestAssertions:
    """Custom assertion helpers for tests."""

    @staticmethod
    def assert_valid_provider_response(response: ProviderResponse):
        """Assert that a provider response is valid."""
        assert response.content is not None
        assert isinstance(response.content, list)
        assert response.stop_reason in ["end_turn", "tool_use", "max_tokens"]

    @staticmethod
    def assert_valid_tool_result(result: dict):
        """Assert that a tool result is valid."""
        assert "output" in result or "error" in result
        if "output" in result:
            assert isinstance(result["output"], str)


@pytest.fixture
def test_assertions():
    """Provide test assertion helpers."""
    return TestAssertions()
