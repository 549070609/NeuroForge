# PyAgentForge Testing Guide

This document provides comprehensive guidance on testing PyAgentForge, including test philosophy, architecture, execution strategies, and best practices.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Test Architecture](#test-architecture)
- [Quick Reference](#quick-reference)
- [Test Categories](#test-categories)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Test Fixtures](#test-fixtures)
- [Mocking Strategies](#mocking-strategies)
- [Coverage Guidelines](#coverage-guidelines)
- [Performance Testing](#performance-testing)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## Testing Philosophy

PyAgentForge follows a comprehensive testing strategy that ensures reliability, maintainability, and performance across all components.

### Core Principles

1. **Test Pyramid**: Prioritize unit tests over integration tests, and integration tests over E2E tests
2. **Isolation**: Each test should be independent and not rely on other tests
3. **Clarity**: Tests should clearly document expected behavior
4. **Speed**: Fast test execution encourages frequent running
5. **Coverage**: Aim for high coverage but prioritize meaningful tests over percentage metrics

### Test Types Distribution

```
           /\
          /  \        E2E Tests (5-10%)
         /----\       - Complete user workflows
        /      \      - Critical path validation
       /--------\     - Slow but comprehensive
      /          \
     /------------\   Integration Tests (20-30%)
    /              \  - Component interactions
   /----------------\ - API contracts
  /                  \- Medium speed
 /--------------------\
/                      \ Unit Tests (60-70%)
------------------------  - Individual functions/classes
                          - Fast execution
                          - High coverage
```

## Test Architecture

### Directory Structure

```
main/pyagentforge/
├── pyagentforge/          # Source code
│   ├── kernel/            # Core engine
│   ├── core/              # Core features
│   ├── providers/         # LLM providers
│   ├── tools/             # Built-in tools
│   └── plugin/            # Plugin system
│
├── tests/                 # Test suite
│   ├── conftest.py        # Shared fixtures
│   ├── test_config.py     # Test configuration
│   │
│   ├── kernel/            # Kernel tests
│   ├── core/              # Core tests
│   ├── providers/         # Provider tests
│   ├── tools/             # Tool tests
│   ├── plugin/            # Plugin tests
│   ├── integration/       # Integration tests
│   ├── e2e/               # End-to-end tests
│   ├── performance/       # Performance tests
│   └── boundary/          # Boundary tests
│
└── TESTING.md             # This file
```

### Test Dependencies

```
pytest>=8.0.0           # Test framework
pytest-asyncio>=0.23.0  # Async test support
pytest-cov>=4.1.0       # Coverage reporting
pytest-xdist>=3.0.0     # Parallel execution (optional)
```

## Quick Reference

### Essential Commands

```bash
# Run all tests
pytest

# Run specific category
pytest tests/kernel/

# Run with coverage
pytest --cov=pyagentforge --cov-report=html

# Run in parallel
pytest -n auto

# Run failed tests only
pytest --lf

# Verbose output
pytest -v --tb=short
```

### Test Markers

| Marker | Purpose | Usage |
|--------|---------|-------|
| `@pytest.mark.asyncio` | Async tests | Required for async test functions |
| `@pytest.mark.slow` | Slow tests | Skipped by default with `-m "not slow"` |
| `@pytest.mark.skipif` | Conditional skip | Skip based on condition |
| `@pytest.mark.xfail` | Expected failure | Test expected to fail |

### Key Fixtures

| Fixture | Description | Scope |
|---------|-------------|-------|
| `mock_provider` | Basic mock LLM provider | Function |
| `tool_registry` | Registry with builtin tools | Function |
| `context_manager` | Message context manager | Function |
| `temp_workspace` | Temporary file workspace | Function |
| `test_settings` | Test configuration | Function |

## Test Categories

### 1. Unit Tests (Kernel, Core, Providers, Tools, Plugin)

Unit tests verify individual components in isolation.

**Location**: `tests/kernel/`, `tests/core/`, `tests/providers/`, `tests/tools/`, `tests/plugin/`

**Characteristics**:
- Fast execution (< 100ms per test)
- No external dependencies
- Mock all external calls
- Test one component at a time

**Example**:
```python
class TestAgentEngineSimpleRun:
    @pytest.mark.asyncio
    async def test_simple_run_returns_text_response(self, mock_provider, tool_registry):
        """Test that a simple run returns the expected text response."""
        engine = AgentEngine(provider=mock_provider, tool_registry=tool_registry)

        result = await engine.run("Hello")

        assert result == "Expected response"
        assert mock_provider.call_count == 1
```

### 2. Integration Tests

Integration tests verify that multiple components work together correctly.

**Location**: `tests/integration/`

**Characteristics**:
- Medium execution time (100ms - 1s)
- Test component interactions
- May use real implementations for some components
- Focus on API contracts and data flow

**Example**:
```python
class TestSimpleToolExecutionFlow:
    @pytest.mark.asyncio
    async def test_single_tool_execution_flow(self):
        """
        Test complete flow: User prompt -> LLM calls tool -> Tool executes -> Result fed back
        """
        # Setup with real components
        registry = ToolRegistry()
        registry.register(SimpleTool())

        # Execute and verify
        engine = AgentEngine(provider=mock_provider, tool_registry=registry)
        result = await engine.run("Use the tool")

        assert tool.execute_count == 1
        assert "success" in result
```

### 3. End-to-End (E2E) Tests

E2E tests verify complete user workflows from start to finish.

**Location**: `tests/e2e/`

**Characteristics**:
- Slow execution (> 1s)
- Test complete workflows
- Minimal mocking
- Validate user-facing behavior

**Example**:
```python
class TestCompleteUserWorkflows:
    @pytest.mark.asyncio
    async def test_file_analysis_workflow(self, e2e_setup):
        """
        Workflow:
        1. User requests file analysis
        2. Agent reads file using tool
        3. Agent analyzes content
        4. Agent provides feedback
        """
        engine = e2e_setup["engine"]

        result = await engine.run("Please analyze the main.py file")

        assert result is not None
        assert "analyzed" in result.lower()
```

### 4. Performance Tests

Performance tests measure system performance under various conditions.

**Location**: `tests/performance/`

**Characteristics**:
- Measure timing and throughput
- Stress testing
- Memory efficiency
- Marked with `@pytest.mark.slow`

**Example**:
```python
class TestCorePerformance:
    @pytest.mark.asyncio
    async def test_simple_message_performance(self, perf_setup):
        """Requirements: Average response time < 50ms"""
        engine = perf_setup["engine"]

        result = await benchmark_async(
            lambda: engine.run("Hello"),
            iterations=50
        )

        assert result.avg_time < 0.05  # 50ms
        assert result.errors == 0
```

### 5. Boundary Tests

Boundary tests verify edge cases and system limits.

**Location**: `tests/boundary/`

**Characteristics**:
- Test empty/null inputs
- Test extremely large inputs
- Test Unicode and special characters
- Test system limits

**Example**:
```python
class TestInputBoundaries:
    @pytest.mark.asyncio
    async def test_extremely_long_input(self, boundary_setup):
        """Test handling of 100KB input"""
        engine = boundary_setup["engine"]
        long_input = generate_large_text(size_kb=100)

        result = await engine.run(long_input)

        assert result is not None  # Should not crash
```

## Running Tests

### Basic Execution

```bash
# All tests
pytest

# Specific directory
pytest tests/kernel/

# Specific file
pytest tests/kernel/test_engine.py

# Specific test
pytest tests/kernel/test_engine.py::TestAgentEngineSimpleRun::test_simple_run_returns_text_response

# Verbose output
pytest -v

# Very verbose (including print statements)
pytest -v -s
```

### Filtering Tests

```bash
# By keyword
pytest -k "engine"

# By marker
pytest -m "asyncio"

# Exclude slow tests
pytest -m "not slow"

# Only slow tests
pytest -m "slow"

# Failed tests only
pytest --lf

# First fail, then rest
pytest --ff
```

### Coverage

```bash
# Basic coverage
pytest --cov=pyagentforge

# HTML report
pytest --cov=pyagentforge --cov-report=html
open htmlcov/index.html

# Terminal report with missing lines
pytest --cov=pyagentforge --cov-report=term-missing

# Fail under threshold
pytest --cov=pyagentforge --cov-fail-under=80
```

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Auto-detect workers
pytest -n auto

# Specific number of workers
pytest -n 4

# Distributed by load
pytest --dist=loadscope
```

### Debug Mode

```bash
# Stop on first failure
pytest -x

# Enter debugger on failure
pytest --pdb

# Show local variables
pytest -l

# Full traceback
pytest --tb=long

# No traceback (just failures)
pytest --tb=no
```

## Writing Tests

### Test Naming Conventions

```python
# File: test_<module>.py
# Class: Test<Feature>
# Method: test_<scenario>_<expected_result>

# Good
class TestAgentEngine:
    def test_run_with_valid_input_returns_response(self):
        pass

    def test_run_with_empty_input_handles_gracefully(self):
        pass

# Avoid
class TestEngine:  # Too generic
    def test_stuff(self):  # Not descriptive
        pass
```

### Test Structure (AAA Pattern)

```python
@pytest.mark.asyncio
async def test_feature_behavior():
    # ARRANGE - Set up test data and conditions
    engine = AgentEngine(provider=mock_provider, tool_registry=registry)
    expected = "Expected result"

    # ACT - Execute the code under test
    result = await engine.run("Hello")

    # ASSERT - Verify the outcome
    assert result == expected
    assert mock_provider.call_count == 1
```

### Testing Async Code

```python
# Always use @pytest.mark.asyncio decorator
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None

# Testing async context managers
@pytest.mark.asyncio
async def test_async_context():
    async with async_resource() as resource:
        result = await resource.do_something()
        assert result is not None

# Testing async generators
@pytest.mark.asyncio
async def test_async_generator():
    results = []
    async for item in async_generator():
        results.append(item)
    assert len(results) == 3
```

### Testing Exceptions

```python
# Test that exception is raised
def test_invalid_input_raises_error():
    with pytest.raises(ValueError, match="Invalid input"):
        validate_input("invalid")

# Test exception attributes
def test_exception_contains_details():
    with pytest.raises(CustomError) as exc_info:
        raise CustomError("message", code=500)

    assert exc_info.value.code == 500

# Test no exception
def test_valid_input_no_error():
    result = validate_input("valid")  # Should not raise
    assert result is True
```

### Parameterized Tests

```python
# Simple parameterization
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_uppercase(input, expected):
    assert uppercase(input) == expected

# Multiple parameterization
@pytest.mark.parametrize("x", [1, 2, 3])
@pytest.mark.parametrize("y", [10, 20])
def test_multiply(x, y):
    assert multiply(x, y) == x * y

# With IDs
@pytest.mark.parametrize("input,expected", [
    ("small", "SMALL"),
    ("large_text" * 100, "LARGE_TEXT"),
], ids=["small", "large"])
def test_with_ids(input, expected):
    pass
```

## Test Fixtures

### Built-in Fixtures (conftest.py)

```python
# Use built-in fixtures
@pytest.mark.asyncio
async def test_with_fixtures(mock_provider, tool_registry, context_manager):
    engine = AgentEngine(
        provider=mock_provider,
        tool_registry=tool_registry,
        context=context_manager,
    )
    result = await engine.run("Hello")
    assert result is not None
```

### Creating Custom Fixtures

```python
# Simple fixture
@pytest.fixture
def simple_component():
    return Component()

# Fixture with setup/teardown
@pytest.fixture
def resource_with_cleanup():
    resource = Resource()
    resource.setup()
    yield resource  # Test runs here
    resource.cleanup()

# Async fixture
@pytest.fixture
async def async_resource():
    resource = await AsyncResource.create()
    yield resource
    await resource.close()

# Fixture with parameters
@pytest.fixture(params=["option1", "option2"])
def configured_component(request):
    return Component(option=request.param)

# Scoped fixtures
@pytest.fixture(scope="module")
def expensive_setup():
    return create_expensive_resource()

@pytest.fixture(scope="session")
def shared_resource():
    return SharedResource()
```

### Fixture Dependencies

```python
# Fixtures can depend on other fixtures
@pytest.fixture
def engine(mock_provider, tool_registry):
    return AgentEngine(provider=mock_provider, tool_registry=tool_registry)

# Using the composed fixture
@pytest.mark.asyncio
async def test_with_composed_fixture(engine):
    result = await engine.run("Hello")
    assert result is not None
```

## Mocking Strategies

### Mocking Providers

```python
# Basic mock provider
class MockProvider:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0

    async def create_message(self, system, messages, tools=None, **kwargs):
        self.call_count += 1
        if self.responses:
            return self.responses.pop(0)
        return ProviderResponse(
            content=[TextBlock(text="Default response")],
            stop_reason="end_turn"
        )

# Using the mock
def test_with_mock_provider():
    provider = MockProvider(responses=[
        ProviderResponse(content=[TextBlock(text="First")], stop_reason="end_turn"),
        ProviderResponse(content=[TextBlock(text="Second")], stop_reason="end_turn"),
    ])
    # Use mock in tests
```

### Mocking Tools

```python
# Mock tool
class MockTool(BaseTool):
    name = "mock_tool"
    description = "Mock tool"
    execute_count = 0

    async def execute(self, **kwargs):
        self.execute_count += 1
        return "Mock result"

# Register mock tool
def test_with_mock_tool():
    registry = ToolRegistry()
    mock_tool = MockTool()
    registry.register(mock_tool)

    # Test using mock tool
```

### Using unittest.mock

```python
from unittest.mock import AsyncMock, MagicMock, patch

# AsyncMock for async functions
mock_provider = AsyncMock()
mock_provider.create_message.return_value = response

# MagicMock for objects
mock_registry = MagicMock()
mock_registry.get.return_value = tool

# Patching
with patch('module.function', return_value="mocked"):
    result = function()

# Async patching
@patch('module.async_function', new_callable=AsyncMock)
async def test_patched(mock_func):
    mock_func.return_value = "mocked"
    result = await async_function()
```

## Coverage Guidelines

### Coverage Targets

| Component | Target | Rationale |
|-----------|--------|-----------|
| Kernel | 90%+ | Core functionality |
| Core | 85%+ | Important features |
| Providers | 80%+ | External integrations |
| Tools | 85%+ | User-facing functionality |
| Plugin | 75%+ | Extension points |

### What to Cover

1. **Happy paths**: Normal operation scenarios
2. **Error handling**: Exception cases
3. **Edge cases**: Boundary conditions
4. **Integration points**: Component interactions

### What Not to Cover

1. **Third-party code**: Already tested by vendors
2. **Simple getters/setters**: Trivial code
3. **Debug/logging code**: Development utilities
4. **Platform-specific code**: Conditional branches

### Coverage Commands

```bash
# Generate coverage report
pytest --cov=pyagentforge --cov-report=html

# View report
open htmlcov/index.html

# Check specific file coverage
pytest --cov=pyagentforge.kernel.engine --cov-report=term-missing
```

## Performance Testing

### Benchmark Utilities

```python
from tests.test_config import PerformanceMetrics

async def benchmark_async(func, iterations=100, warmup=10):
    """Benchmark an async function."""
    metrics = PerformanceMetrics()

    # Warmup
    for _ in range(warmup):
        await func()

    # Benchmark
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        elapsed = time.perf_counter() - start
        metrics.add_result(elapsed)

    return metrics
```

### Performance Test Patterns

```python
class TestPerformance:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_throughput(self):
        """Test operations per second."""
        metrics = await benchmark_async(lambda: engine.run("Hello"))

        assert metrics.ops_per_second > 100
        assert metrics.avg_time < 0.01  # 10ms
```

### Stress Testing

```python
@pytest.mark.asyncio
@pytest.mark.slow
async def test_high_concurrent_load():
    """Test handling 100 concurrent operations."""
    results = await asyncio.gather(
        *[run_engine() for _ in range(100)],
        return_exceptions=True
    )

    successful = sum(1 for r in results if not isinstance(r, Exception))
    assert successful >= 95  # 95% success rate
```

## CI/CD Integration

### GitHub Actions Configuration

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

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
        python -m pip install --upgrade pip
        pip install -e ".[dev]"

    - name: Lint with ruff
      run: |
        pip install ruff
        ruff check .

    - name: Run tests
      run: |
        pytest --cov=pyagentforge --cov-report=xml --cov-report=html

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

    - name: Archive coverage report
      uses: actions/upload-artifact@v3
      with:
        name: coverage-report
        path: htmlcov/
```

### Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest -x -q
        language: system
        pass_filenames: false
        always_run: true
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```bash
# Problem
ModuleNotFoundError: No module named 'pyagentforge'

# Solution
pip install -e ".[dev]"
```

#### 2. Async Test Warnings

```python
# Problem: PytestUnhandledCoroutineWarning

# Solution: Add decorator
@pytest.mark.asyncio
async def test_something():
    result = await async_function()
```

#### 3. Fixture Not Found

```python
# Problem: fixture 'xxx' not found

# Solution: Ensure fixture is in conftest.py or same file
# conftest.py
@pytest.fixture
def xxx():
    return "value"
```

#### 4. Event Loop Issues

```python
# Problem: Task got Future attached to a different loop

# Solution: Use session-scoped loop in conftest.py
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

#### 5. Test Intermittent Failures

```bash
# Run multiple times to detect flaky tests
pytest --count=5 tests/specific_test.py
```

### Debugging Techniques

```python
# Add print statements (visible with -s flag)
def test_something():
    result = function()
    print(f"Debug: result = {result}")  # pytest -s
    assert result is not None

# Use pdb debugger
def test_something():
    result = function()
    import pdb; pdb.set_trace()
    assert result is not None

# pytest --pdb for post-mortem debugging
# pytest --trace for tracing
```

### Getting Help

1. **Check pytest documentation**: https://docs.pytest.org/
2. **Check pytest-asyncio**: https://pytest-asyncio.readthedocs.io/
3. **Review existing tests**: Similar tests often show patterns
4. **Check GitHub issues**: Known issues and solutions

---

For more details, see the [tests/README.md](tests/README.md) file.
