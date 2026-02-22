# PyAgentForge Test Suite

This directory contains the comprehensive test suite for PyAgentForge. The tests are organized by category and cover unit tests, integration tests, end-to-end tests, performance tests, and boundary condition tests.

## Table of Contents

- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Test Categories](#test-categories)
- [Writing New Tests](#writing-new-tests)
- [Debugging Failed Tests](#debugging-failed-tests)
- [CI/CD Integration](#cicd-integration)

## Quick Start

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=pyagentforge --cov-report=html
```

## Running Tests

### Run All Tests

```bash
# Run all tests with default settings
pytest

# Run with verbose output and short tracebacks
pytest -v --tb=short

# Run with full tracebacks for debugging
pytest --tb=long
```

### Run Specific Test Categories

```bash
# Kernel tests (core engine components)
pytest tests/kernel/

# Core tests (concurrency, background tasks, etc.)
pytest tests/core/

# Provider tests (OpenAI, Anthropic, Google)
pytest tests/providers/

# Tool tests (built-in tools)
pytest tests/tools/

# Plugin tests (plugin system)
pytest tests/plugin/

# Integration tests (end-to-end flows)
pytest tests/integration/

# E2E tests (complete user workflows)
pytest tests/e2e/

# Performance tests (benchmarks and stress tests)
pytest tests/performance/

# Boundary tests (edge cases and limits)
pytest tests/boundary/
```

### Run Specific Test Files

```bash
# Run a specific test file
pytest tests/kernel/test_engine.py

# Run a specific test class
pytest tests/kernel/test_engine.py::TestAgentEngineSimpleRun

# Run a specific test method
pytest tests/kernel/test_engine.py::TestAgentEngineSimpleRun::test_simple_run_returns_text_response
```

### Run with Coverage

```bash
# Run with coverage report
pytest --cov=pyagentforge

# Run with HTML coverage report
pytest --cov=pyagentforge --cov-report=html
open htmlcov/index.html

# Run with detailed coverage report
pytest --cov=pyagentforge --cov-report=term-missing
```

### Run Tests in Parallel

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (auto-detect CPU count)
pytest -n auto

# Run with specific number of workers
pytest -n 4
```

### Run Slow Tests

```bash
# Include slow tests (marked with @pytest.mark.slow)
pytest --run-slow

# Skip slow tests (default behavior)
pytest -m "not slow"
```

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared pytest fixtures
├── test_config.py           # Test configuration and utilities
├── run_tests.py             # Custom test runner
├── run_coverage.py          # Coverage report generator
│
├── kernel/                  # Kernel layer tests
│   ├── __init__.py
│   ├── test_engine.py       # AgentEngine tests
│   ├── test_executor.py     # ToolExecutor tests
│   ├── test_context.py      # ContextManager tests
│   └── test_message.py      # Message class tests
│
├── core/                    # Core feature tests
│   ├── __init__.py
│   ├── test_concurrency_manager.py
│   ├── test_background_manager.py
│   ├── test_category_registry.py
│   └── test_category.py
│
├── providers/               # Provider implementation tests
│   ├── __init__.py
│   ├── test_base_provider.py
│   ├── test_anthropic_provider.py
│   ├── test_openai_provider.py
│   ├── test_google_provider.py
│   └── test_factory.py
│
├── tools/                   # Built-in tool tests
│   ├── __init__.py
│   ├── test_registry.py
│   ├── test_permission.py
│   ├── test_bash.py
│   ├── test_read.py
│   ├── test_write.py
│   ├── test_edit.py
│   ├── test_glob.py
│   └── test_grep.py
│
├── plugin/                  # Plugin system tests
│   ├── __init__.py
│   ├── test_manager.py
│   ├── test_hooks.py
│   └── test_dependencies.py
│
├── integration/             # Integration tests
│   ├── __init__.py
│   ├── test_engine_integration.py
│   ├── test_background_concurrency.py
│   └── test_task_system.py
│
├── e2e/                     # End-to-end tests
│   └── __init__.py
│
├── performance/             # Performance tests
│   └── __init__.py
│
└── boundary/                # Boundary condition tests
    └── __init__.py
```

## Test Categories

### 1. Kernel Tests (`tests/kernel/`)

Tests for the core engine components:

- **test_engine.py**: AgentEngine - main execution loop, tool calling, context management
- **test_executor.py**: ToolExecutor - tool execution, permission checking, timeouts
- **test_context.py**: ContextManager - message history, truncation, context window
- **test_message.py**: Message classes - message formatting, content blocks

### 2. Core Tests (`tests/core/`)

Tests for core features and utilities:

- **test_concurrency_manager.py**: Concurrency limits, semaphores, queue management
- **test_background_manager.py**: Background task execution, notifications
- **test_category_registry.py**: Task classification, category registration
- **test_category.py**: Category definitions, complexity levels

### 3. Provider Tests (`tests/providers/`)

Tests for LLM provider implementations:

- **test_base_provider.py**: Base provider interface, common functionality
- **test_anthropic_provider.py**: Anthropic Claude API integration
- **test_openai_provider.py**: OpenAI GPT API integration
- **test_google_provider.py**: Google Gemini API integration
- **test_factory.py**: Provider factory, model selection

### 4. Tool Tests (`tests/tools/`)

Tests for built-in tools:

- **test_registry.py**: Tool registration, discovery, schema generation
- **test_permission.py**: Permission checking, allow/deny lists
- **test_bash.py**: Bash command execution
- **test_read.py**: File reading
- **test_write.py**: File writing
- **test_edit.py**: File editing
- **test_glob.py**: File pattern matching
- **test_grep.py**: Content searching

### 5. Plugin Tests (`tests/plugin/`)

Tests for the plugin system:

- **test_manager.py**: Plugin loading, lifecycle management
- **test_hooks.py**: Hook system, event emission
- **test_dependencies.py**: Dependency resolution, loading order

### 6. Integration Tests (`tests/integration/`)

Tests that verify multiple components work together:

- **test_engine_integration.py**: Complete Engine-Tools-Provider flow
- **test_background_concurrency.py**: Background tasks with concurrency limits
- **test_task_system.py**: Task persistence and management

### 7. E2E Tests (`tests/e2e/`)

End-to-end tests simulating complete user workflows:

- Complete user conversations
- Multi-turn interactions
- Error recovery scenarios
- Context management across sessions

### 8. Performance Tests (`tests/performance/`)

Performance benchmarks and stress tests:

- Response time benchmarks
- Throughput measurements
- Memory efficiency tests
- Concurrent load tests
- Sustained load tests

### 9. Boundary Tests (`tests/boundary/`)

Edge case and boundary condition tests:

- Empty/null inputs
- Extremely large inputs
- Unicode and special characters
- Maximum iteration limits
- Concurrency limits

## Writing New Tests

### Basic Test Structure

```python
"""
Tests for [Component Name]

Detailed description of what is being tested.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from pyagentforge.module import Component


class TestComponentFeature:
    """Tests for a specific feature of the component."""

    @pytest.fixture
    def setup_component(self):
        """Create a component instance for testing."""
        return Component()

    @pytest.mark.asyncio
    async def test_feature_behavior(self, setup_component):
        """
        Test description.

        Flow:
        1. Setup condition
        2. Execute action
        3. Verify result
        """
        component = setup_component

        # Execute
        result = await component.do_something()

        # Verify
        assert result is not None
        assert result.status == "expected"
```

### Using Fixtures

```python
# Use shared fixtures from conftest.py
@pytest.mark.asyncio
async def test_with_shared_fixtures(mock_provider, tool_registry, context_manager):
    """Test using shared fixtures."""
    engine = AgentEngine(
        provider=mock_provider,
        tool_registry=tool_registry,
        context=context_manager,
    )
    result = await engine.run("Hello")
    assert result is not None
```

### Custom Fixtures

```python
@pytest.fixture
def custom_setup():
    """Create custom test setup."""
    component = CustomComponent()
    component.configure(option="value")
    yield component
    component.cleanup()  # Teardown
```

### Test Markers

```python
# Async test
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None

# Slow test (skipped by default)
@pytest.mark.slow
def test_slow_operation():
    time.sleep(10)
    assert True

# Skip test conditionally
@pytest.mark.skipif(not has_api_key(), reason="Requires API key")
def test_with_api():
    pass

# Expected to fail
@pytest.mark.xfail(reason="Known bug #123")
def test_known_bug():
    pass
```

### Test Data

```python
from tests.test_config import SAMPLE_FILE_CONTENTS, SAMPLE_PROMPTS

def test_with_sample_data():
    content = SAMPLE_FILE_CONTENTS["python"]
    assert "def " in content
```

## Debugging Failed Tests

### Verbose Output

```bash
# Show full test output
pytest -v -s

# Show local variables on failure
pytest -l

# Show full traceback
pytest --tb=long

# Enter debugger on failure
pytest --pdb
```

### Interactive Debugging

```python
# Add breakpoint in test
def test_something():
    result = some_function()
    import pdb; pdb.set_trace()  # Debugger breakpoint
    assert result is not None
```

### Isolating Failures

```bash
# Run only failed tests from last run
pytest --lf

# Run tests that would have failed first
pytest --ff

# Exit on first failure
pytest -x
```

### Common Issues

1. **Import errors**: Ensure `pyagentforge` is installed in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Async test warnings**: Use `@pytest.mark.asyncio` decorator for async tests.

3. **Fixture not found**: Check that fixtures are defined in `conftest.py` or the same file.

4. **Timeout errors**: Increase timeout for slow tests or mock external calls.

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -e ".[dev]"

    - name: Run tests
      run: |
        pytest --cov=pyagentforge --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

```bash
# Install pre-commit
pip install pre-commit

# Add to .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest -x
        language: system
        pass_filenames: false
        always_run: true

# Install the hook
pre-commit install
```

### Coverage Requirements

```bash
# Fail if coverage is below threshold
pytest --cov=pyagentforge --cov-fail-under=80
```

## Test Configuration

The test configuration is defined in:

- `pyproject.toml` - pytest configuration
- `tests/conftest.py` - shared fixtures
- `tests/test_config.py` - test constants and utilities

### pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"
markers = [
    "slow: marks tests as slow",
]

[tool.coverage.run]
source = ["pyagentforge"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
]
```

## Best Practices

1. **Test names should be descriptive**: `test_engine_handles_tool_timeout_gracefully`

2. **One concept per test**: Each test should verify one specific behavior.

3. **Use AAA pattern**: Arrange, Act, Assert

4. **Avoid test interdependence**: Tests should not depend on each other.

5. **Mock external dependencies**: Don't make real API calls in unit tests.

6. **Test edge cases**: Include boundary conditions and error cases.

7. **Keep tests fast**: Slow tests discourage running the suite.

8. **Update tests with code changes**: Keep tests in sync with implementation.

---

For more information, see the main [TESTING.md](../TESTING.md) file.
