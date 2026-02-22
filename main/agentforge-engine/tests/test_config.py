"""
PyAgentForge Test Configuration

Central configuration module for test constants, utilities, and helpers.
This module provides shared test configuration values and utility functions
used across all test modules.
"""

import os
import tempfile
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# Test Environment Configuration
# ============================================================================

class TestEnvironment(Enum):
    """Test environment types."""
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    BOUNDARY = "boundary"


@dataclass
class TestConfig:
    """Configuration for test execution."""
    # Environment settings
    environment: TestEnvironment = TestEnvironment.UNIT
    debug: bool = False
    verbose: bool = True

    # Timeout settings (in seconds)
    default_timeout: float = 30.0
    slow_test_timeout: float = 60.0
    integration_timeout: float = 120.0
    e2e_timeout: float = 300.0

    # Performance test settings
    performance_iterations: int = 100
    performance_warmup_iterations: int = 10

    # Mock provider settings
    mock_response_delay: float = 0.01

    # Context settings
    default_max_messages: int = 100
    default_max_tokens: int = 4000
    small_max_messages: int = 5
    small_max_tokens: int = 100

    # Tool execution settings
    default_tool_timeout: float = 30.0
    short_tool_timeout: float = 0.5

    # Concurrency settings
    max_concurrent_tasks: int = 10
    max_concurrent_tools: int = 5


# Default test configuration instance
DEFAULT_CONFIG = TestConfig()


# ============================================================================
# Test Constants
# ============================================================================

# API Keys for testing (mock values)
TEST_ANTHROPIC_API_KEY = "test-anthropic-key-12345"
TEST_OPENAI_API_KEY = "test-openai-key-12345"
TEST_GOOGLE_API_KEY = "test-google-key-12345"

# Model names for testing
TEST_MODELS = {
    "anthropic": "claude-3-opus-20240229",
    "openai": "gpt-4-turbo-preview",
    "google": "gemini-pro",
    "mock": "test-model",
}

# Sample prompts for testing
SAMPLE_PROMPTS = {
    "simple": "Hello, how are you?",
    "tool_use": "Please read the file /tmp/test.txt",
    "multi_step": "First read the config file, then validate it, and finally save the results.",
    "complex": "Analyze the codebase, identify potential issues, create a report, and suggest improvements.",
    "streaming": "Write a long essay about AI agents.",
}

# Sample file contents for testing
SAMPLE_FILE_CONTENTS = {
    "python": '''
def hello_world():
    """A simple hello world function."""
    print("Hello, World!")
    return "success"

if __name__ == "__main__":
    hello_world()
''',
    "yaml": '''
version: "1.0"
config:
  debug: true
  max_retries: 3
  timeout: 30
''',
    "markdown": '''
# Test Document

This is a test markdown file for testing purposes.

## Section 1

Some content here.

## Section 2

More content here.
''',
    "json": '''
{
    "name": "test",
    "version": "1.0.0",
    "config": {
        "enabled": true,
        "count": 42
    }
}
''',
}


# ============================================================================
# Sample Test Data
# ============================================================================

@dataclass
class SampleToolInput:
    """Sample tool input for testing."""
    name: str
    arguments: dict[str, Any]
    expected_output: str = ""
    should_fail: bool = False


SAMPLE_TOOL_INPUTS = [
    SampleToolInput(
        name="read",
        arguments={"file_path": "/tmp/test.txt"},
        expected_output="File content read successfully",
    ),
    SampleToolInput(
        name="write",
        arguments={"file_path": "/tmp/output.txt", "content": "Test content"},
        expected_output="File written successfully",
    ),
    SampleToolInput(
        name="bash",
        arguments={"command": "echo 'hello'"},
        expected_output="hello",
    ),
    SampleToolInput(
        name="nonexistent_tool",
        arguments={},
        expected_output="Tool not found",
        should_fail=True,
    ),
]


# ============================================================================
# Utility Functions
# ============================================================================

def create_temp_file(content: str, suffix: str = ".txt", prefix: str = "test_") -> Path:
    """
    Create a temporary file with the given content.

    Args:
        content: Content to write to the file.
        suffix: File suffix/extension.
        prefix: File name prefix.

    Returns:
        Path to the created temporary file.
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    try:
        os.write(fd, content.encode('utf-8'))
    finally:
        os.close(fd)
    return Path(path)


def create_temp_directory(prefix: str = "test_dir_") -> Path:
    """
    Create a temporary directory.

    Args:
        prefix: Directory name prefix.

    Returns:
        Path to the created temporary directory.
    """
    return Path(tempfile.mkdtemp(prefix=prefix))


def create_test_workspace() -> dict[str, Path]:
    """
    Create a test workspace with sample files.

    Returns:
        Dictionary mapping file names to their paths.
    """
    workspace = create_temp_directory(prefix="test_workspace_")
    files = {}

    # Create Python file
    py_file = workspace / "main.py"
    py_file.write_text(SAMPLE_FILE_CONTENTS["python"])
    files["main.py"] = py_file

    # Create YAML config
    yaml_file = workspace / "config.yaml"
    yaml_file.write_text(SAMPLE_FILE_CONTENTS["yaml"])
    files["config.yaml"] = yaml_file

    # Create Markdown README
    md_file = workspace / "README.md"
    md_file.write_text(SAMPLE_FILE_CONTENTS["markdown"])
    files["README.md"] = md_file

    # Create JSON file
    json_file = workspace / "data.json"
    json_file.write_text(SAMPLE_FILE_CONTENTS["json"])
    files["data.json"] = json_file

    # Create subdirectory with files
    src_dir = workspace / "src"
    src_dir.mkdir()
    src_file = src_dir / "utils.py"
    src_file.write_text("# Utility functions\n")
    files["src/utils.py"] = src_file

    return {
        "workspace": workspace,
        "files": files,
    }


def assert_valid_provider_response(response: Any) -> None:
    """
    Assert that a provider response has a valid structure.

    Args:
        response: The response to validate.

    Raises:
        AssertionError: If the response is invalid.
    """
    assert response is not None, "Response cannot be None"
    assert hasattr(response, 'content'), "Response must have 'content' attribute"
    assert hasattr(response, 'stop_reason'), "Response must have 'stop_reason' attribute"
    assert response.stop_reason in ["end_turn", "tool_use", "max_tokens"], \
        f"Invalid stop_reason: {response.stop_reason}"


def assert_valid_tool_result(result: dict[str, Any]) -> None:
    """
    Assert that a tool result has a valid structure.

    Args:
        result: The tool result to validate.

    Raises:
        AssertionError: If the result is invalid.
    """
    assert isinstance(result, dict), "Tool result must be a dictionary"
    assert "output" in result or "error" in result, \
        "Tool result must have 'output' or 'error' key"


def generate_large_text(size_kb: int = 100) -> str:
    """
    Generate a large text string for testing.

    Args:
        size_kb: Size of the text in kilobytes.

    Returns:
        Generated text string.
    """
    # Generate approximately size_kb of text
    base_text = "This is a test line for generating large text content. " * 10
    lines_needed = (size_kb * 1024) // len(base_text.encode('utf-8'))
    return "\n".join([f"Line {i}: {base_text}" for i in range(lines_needed)])


def calculate_expected_tokens(text: str) -> int:
    """
    Calculate approximate token count for a text.

    This is a simple approximation: ~4 characters per token.

    Args:
        text: Text to calculate tokens for.

    Returns:
        Approximate token count.
    """
    return len(text) // 4


# ============================================================================
# Test Markers and Skip Conditions
# ============================================================================

def skip_if_no_api_key(provider: str) -> bool:
    """
    Check if API key is available for a provider.

    Args:
        provider: Provider name ('anthropic', 'openai', 'google').

    Returns:
        True if should skip (no API key), False otherwise.
    """
    env_var_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    env_var = env_var_map.get(provider.lower())
    if not env_var:
        return True
    return not bool(os.environ.get(env_var))


def requires_api_key(provider: str) -> str:
    """
    Get skip reason for API key requirement.

    Args:
        provider: Provider name.

    Returns:
        Skip reason string.
    """
    return f"Requires {provider.upper()}_API_KEY environment variable"


# ============================================================================
# Performance Testing Utilities
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Performance metrics for a test run."""
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    iterations: int = 0
    errors: int = 0
    times: list[float] = field(default_factory=list)

    def add_result(self, time: float, error: bool = False) -> None:
        """Add a timing result."""
        self.times.append(time)
        self.total_time += time
        self.min_time = min(self.min_time, time)
        self.max_time = max(self.max_time, time)
        self.iterations += 1
        if error:
            self.errors += 1
        if self.iterations > 0:
            self.avg_time = self.total_time / self.iterations

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_time": self.total_time,
            "min_time": self.min_time if self.min_time != float('inf') else 0,
            "max_time": self.max_time,
            "avg_time": self.avg_time,
            "iterations": self.iterations,
            "errors": self.errors,
        }


# ============================================================================
# Test Data Generators
# ============================================================================

def generate_test_messages(count: int, include_tool_calls: bool = False) -> list[dict[str, Any]]:
    """
    Generate a list of test messages.

    Args:
        count: Number of messages to generate.
        include_tool_calls: Whether to include tool call messages.

    Returns:
        List of message dictionaries.
    """
    messages = []
    for i in range(count):
        if i % 2 == 0:
            # User message
            messages.append({
                "role": "user",
                "content": f"Test message {i}"
            })
        else:
            # Assistant message
            if include_tool_calls and i % 4 == 3:
                messages.append({
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": f"Response {i}"},
                        {
                            "type": "tool_use",
                            "id": f"tool_{i}",
                            "name": "test_tool",
                            "input": {"arg": f"value_{i}"}
                        }
                    ]
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": f"Response {i}"
                })
    return messages


def generate_tool_definitions(count: int) -> list[dict[str, Any]]:
    """
    Generate a list of tool definitions.

    Args:
        count: Number of tool definitions to generate.

    Returns:
        List of tool definition dictionaries.
    """
    tools = []
    for i in range(count):
        tools.append({
            "name": f"test_tool_{i}",
            "description": f"Test tool number {i}",
            "input_schema": {
                "type": "object",
                "properties": {
                    "arg1": {"type": "string"},
                    "arg2": {"type": "number"},
                },
                "required": ["arg1"]
            }
        })
    return tools
