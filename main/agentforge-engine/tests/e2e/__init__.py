"""
E2E (End-to-End) Tests for PyAgentForge

This module contains end-to-end tests that verify complete user workflows
and system integration from start to finish.
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.registry import ToolRegistry

# ============================================================================
# Mock Components for E2E Tests
# ============================================================================

class E2EMockProvider:
    """Mock provider that simulates realistic multi-turn conversations."""

    def __init__(self):
        self.model = "e2e-test-model"
        self.max_tokens = 4096
        self.call_count = 0
        self.conversation_log: list[dict[str, Any]] = []

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Simulate realistic responses based on conversation context."""
        self.call_count += 1
        self.conversation_log.append({
            "call": self.call_count,
            "messages_count": len(messages),
            "has_tools": tools is not None,
        })

        # Analyze the last user message to determine response
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    last_user_msg = content
                elif isinstance(content, list):
                    # Handle tool results
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            last_user_msg = block.get("content", "")
                            break
                break

        # Simple response logic based on message content
        if "hello" in last_user_msg.lower():
            return ProviderResponse(
                content=[TextBlock(text="Hello! I'm your AI assistant. How can I help you today?")],
                stop_reason="end_turn",
            )

        if self.call_count == 1 and "analyze" in last_user_msg.lower():
            return ProviderResponse(
                content=[
                    TextBlock(text="I'll analyze the file for you."),
                    ToolUseBlock(
                        id="tool_read_1",
                        name="read",
                        input={"file_path": "/workspace/main.py"}
                    ),
                ],
                stop_reason="tool_use",
            )

        if "file content" in last_user_msg.lower() or "def " in last_user_msg:
            return ProviderResponse(
                content=[TextBlock(text="I've analyzed the file. It contains a Python function. Would you like me to suggest any improvements?")],
                stop_reason="end_turn",
            )

        # Default response
        return ProviderResponse(
            content=[TextBlock(text="I understand. Let me help you with that.")],
            stop_reason="end_turn",
        )

    async def stream_message(self, system: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
        """Mock streaming."""
        response = await self.create_message(system, messages, tools, **kwargs)
        yield response


class SimpleReadTool(BaseTool):
    """Simple mock read tool for E2E tests."""

    name: str = "read"
    description: str = "Read a file"

    async def execute(self, file_path: str, **kwargs) -> str:
        """Simulate reading a file."""
        if "main.py" in file_path:
            return '''def hello_world():
    """A simple hello world function."""
    print("Hello, World!")
    return "success"

if __name__ == "__main__":
    hello_world()
'''
        return f"Content of {file_path}"


# ============================================================================
# E2E Test: Complete User Workflow
# ============================================================================

class TestCompleteUserWorkflows:
    """Tests for complete user workflows from start to finish."""

    @pytest.fixture
    def e2e_setup(self):
        """Set up E2E test environment."""
        provider = E2EMockProvider()
        registry = ToolRegistry()
        registry.register(SimpleReadTool())
        context = ContextManager()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(
                system_prompt="You are a helpful AI coding assistant.",
                max_iterations=20,
            ),
            context=context,
        )

        return {
            "provider": provider,
            "registry": registry,
            "context": context,
            "engine": engine,
        }

    @pytest.mark.asyncio
    async def test_simple_greeting_workflow(self, e2e_setup):
        """
        E2E Test: Simple greeting workflow

        Workflow:
        1. User sends greeting
        2. Agent responds with greeting
        3. Conversation ends gracefully
        """
        engine = e2e_setup["engine"]
        provider = e2e_setup["provider"]

        result = await engine.run("Hello there!")

        assert result is not None
        assert len(result) > 0
        assert "hello" in result.lower() or "assistant" in result.lower()
        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_file_analysis_workflow(self, e2e_setup):
        """
        E2E Test: File analysis workflow

        Workflow:
        1. User requests file analysis
        2. Agent reads file using tool
        3. Agent analyzes content
        4. Agent provides feedback
        """
        engine = e2e_setup["engine"]
        provider = e2e_setup["provider"]

        result = await engine.run("Please analyze the main.py file")

        assert result is not None
        assert provider.call_count >= 1  # At least one LLM call

        # Verify context was updated
        context = e2e_setup["context"]
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_workflow(self, e2e_setup):
        """
        E2E Test: Multi-turn conversation

        Workflow:
        1. User starts conversation
        2. Agent responds
        3. User follows up
        4. Agent uses context from previous turns
        """
        engine = e2e_setup["engine"]
        context = e2e_setup["context"]

        # Turn 1
        result1 = await engine.run("Hello!")
        assert result1 is not None

        # Verify turn 1 context
        messages_after_turn1 = len(context)

        # Turn 2 (using same context)
        engine2 = AgentEngine(
            provider=e2e_setup["provider"],
            tool_registry=e2e_setup["registry"],
            config=AgentConfig(max_iterations=20),
            context=context,
        )
        result2 = await engine2.run("Can you help me with something else?")

        assert result2 is not None
        # Context should have grown
        assert len(context) > messages_after_turn1


# ============================================================================
# E2E Test: Error Recovery Workflows
# ============================================================================

class TestErrorRecoveryWorkflows:
    """Tests for error recovery in complete workflows."""

    @pytest.fixture
    def error_prone_setup(self):
        """Set up environment with error-prone tools."""
        class FailingReadTool(BaseTool):
            name: str = "read"
            description: str = "Read tool that fails"

            async def execute(self, file_path: str, **kwargs) -> str:
                raise PermissionError(f"Cannot access {file_path}")

        provider = E2EMockProvider()
        registry = ToolRegistry()
        registry.register(FailingReadTool())

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        return {"engine": engine, "provider": provider}

    @pytest.mark.asyncio
    async def test_tool_error_recovery_workflow(self, error_prone_setup):
        """
        E2E Test: Recovery from tool errors

        Workflow:
        1. User requests operation
        2. Tool fails
        3. Agent handles error gracefully
        4. Conversation continues
        """
        engine = error_prone_setup["engine"]

        # This should not crash, even though tool fails
        result = await engine.run("Read the file /secret/data.txt")

        assert result is not None
        # Engine should have handled the error


# ============================================================================
# E2E Test: Context Management Workflow
# ============================================================================

class TestContextManagementWorkflows:
    """Tests for context management across conversations."""

    @pytest.mark.asyncio
    async def test_context_persistence_workflow(self):
        """
        E2E Test: Context persistence across sessions

        Workflow:
        1. Create context
        2. Have conversation
        3. Save context state
        4. Restore context in new session
        5. Continue conversation with full history
        """
        provider = E2EMockProvider()
        registry = ToolRegistry()
        context = ContextManager()

        # Session 1
        engine1 = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        await engine1.run("Hello from session 1")
        session1_message_count = len(context)

        # Session 2 (same context)
        engine2 = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        await engine2.run("Hello from session 2")

        # Context should have messages from both sessions
        assert len(context) > session1_message_count

    @pytest.mark.asyncio
    async def test_context_reset_workflow(self):
        """
        E2E Test: Context reset functionality

        Workflow:
        1. Have conversation
        2. Reset context
        3. Verify context is clean
        4. Start fresh conversation
        """
        provider = E2EMockProvider()
        registry = ToolRegistry()
        context = ContextManager()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        # Have conversation
        await engine.run("First message")
        assert len(context) > 0

        # Reset
        engine.reset()
        assert len(context) == 0

        # Fresh start
        await engine.run("Fresh start message")
        assert len(context) > 0


# ============================================================================
# E2E Test: Tool Chaining Workflow
# ============================================================================

class TestToolChainingWorkflows:
    """Tests for tool chaining in complete workflows."""

    @pytest.fixture
    def tool_chain_setup(self):
        """Set up environment with multiple tools."""
        class ReadTool(BaseTool):
            name: str = "read"
            description: str = "Read file"
            execute_count: int = 0

            async def execute(self, file_path: str, **kwargs) -> str:
                self.execute_count += 1
                return "file content"

        class WriteTool(BaseTool):
            name: str = "write"
            description: str = "Write file"
            execute_count: int = 0

            async def execute(self, file_path: str, content: str, **kwargs) -> str:
                self.execute_count += 1
                return "written successfully"

        class BashTool(BaseTool):
            name: str = "bash"
            description: str = "Run bash"
            execute_count: int = 0

            async def execute(self, command: str, **kwargs) -> str:
                self.execute_count += 1
                return "command executed"

        provider = E2EMockProvider()
        registry = ToolRegistry()

        read_tool = ReadTool()
        write_tool = WriteTool()
        bash_tool = BashTool()

        registry.register(read_tool)
        registry.register(write_tool)
        registry.register(bash_tool)

        return {
            "provider": provider,
            "registry": registry,
            "tools": {
                "read": read_tool,
                "write": write_tool,
                "bash": bash_tool,
            },
        }

    @pytest.mark.asyncio
    async def test_multi_tool_workflow(self, tool_chain_setup):
        """
        E2E Test: Multiple tools in workflow

        Workflow:
        1. Agent has access to multiple tools
        2. Agent can use any tool as needed
        3. Tools execute correctly
        """
        engine = AgentEngine(
            provider=tool_chain_setup["provider"],
            tool_registry=tool_chain_setup["registry"],
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Help me with file operations")

        assert result is not None
        # Engine should complete successfully


# ============================================================================
# E2E Test: Performance Workflows
# ============================================================================

class TestPerformanceWorkflows:
    """Tests for performance in real-world scenarios."""

    @pytest.mark.asyncio
    async def test_large_context_handling(self):
        """
        E2E Test: Handle large context efficiently

        Workflow:
        1. Build up large context
        2. Continue conversation
        3. Verify performance is acceptable
        """
        import time

        provider = E2EMockProvider()
        registry = ToolRegistry()
        context = ContextManager(max_messages=100)

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        # Build up context
        for i in range(10):
            await engine.run(f"Message {i}")

        # Time a response with large context
        start = time.time()
        result = await engine.run("Final message")
        elapsed = time.time() - start

        assert result is not None
        # Should respond in reasonable time (< 1 second with mock provider)
        assert elapsed < 1.0
