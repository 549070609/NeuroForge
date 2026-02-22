# Provider Layer Tests

Comprehensive test suite for PyAgentForge's Provider layer.

## Overview

This directory contains **129 test methods** across **5 test files**, providing thorough coverage of all LLM provider functionality.

## Test Files

### 1. test_base_provider.py
Tests for the abstract `BaseProvider` class and common provider functionality.

**Test Coverage (28 tests):**
- Provider initialization with default and custom parameters
- Abstract method implementations
- Token counting functionality
- Message streaming default behavior
- ProviderResponse properties (text, tool_calls, has_tool_calls)
- Edge cases (empty messages, large inputs, missing content)

**Key Test Classes:**
- `TestBaseProvider` - Core provider functionality
- `TestProviderResponse` - Response model validation
- `TestProviderEdgeCases` - Error handling and edge cases

### 2. test_openai_provider.py
Tests for the OpenAI provider implementation.

**Test Coverage (23 tests):**
- Provider initialization with API key and custom base URL
- Message format conversion (simple, tool_use, tool_result)
- Tool format conversion to OpenAI format
- Successful message creation
- Message creation with tool calls
- JSON argument parsing (string, dict, error handling)
- Token counting with tiktoken and fallback
- Message streaming with chunk yielding
- Custom parameters (max_tokens, temperature)
- Stop reason handling (end_turn, tool_use, max_tokens)
- API error handling

**Key Features Tested:**
- `_convert_tools_to_openai()` - Tool format conversion
- `_convert_messages_to_openai()` - Message format conversion
- `create_message()` - Main API interaction
- `count_tokens()` - Token estimation
- `stream_message()` - Streaming support

### 3. test_anthropic_provider.py
Tests for the Anthropic provider implementation.

**Test Coverage (22 tests):**
- Provider initialization with different Claude models
- Successful message creation
- Message creation with single and multiple tool calls
- Temperature parameter handling
- Extra Anthropic parameters (top_p, top_k, stop_sequences)
- Token counting with content blocks
- Message streaming with events
- API error handling
- Message format preservation
- Response property validation

**Key Features Tested:**
- `create_message()` - Direct API pass-through
- `count_tokens()` - Simple token estimation
- `stream_message()` - Streaming with final response
- Temperature conditional inclusion

### 4. test_google_provider.py
Tests for the Google Generative AI provider implementation.

**Test Coverage (27 tests):**
- Lazy client and model initialization
- API key handling (explicit and environment variable)
- Message conversion to Google format (roles: user/model)
- Tool conversion to FunctionDeclaration format
- Successful message creation
- Message creation with function calls
- Token counting with model and fallback
- Message streaming
- JSON Schema conversion
- Response parsing with usage metadata
- Different Gemini model support

**Key Features Tested:**
- `_get_client()` - Lazy client initialization
- `_get_model()` - Lazy model initialization
- `_convert_messages()` - Role conversion (assistant → model)
- `_convert_tools()` - FunctionDeclaration format
- `_parse_response()` - Response parsing

### 5. test_factory.py
Tests for the ModelAdapterFactory and provider creation.

**Test Coverage (29 tests):**
- Factory initialization with custom and default registry
- Provider creation for OpenAI, Anthropic, Google
- Unknown provider/model error handling
- Provider instance caching
- Custom parameters (max_tokens, temperature, base_url)
- Model information retrieval
- Azure/Bedrock import error handling
- Custom provider factory registration
- Convenience functions (create_provider, get_supported_models)
- Singleton factory pattern
- Extra parameters propagation
- Missing API key handling

**Key Features Tested:**
- `create_provider()` - Main factory method
- `get_supported_models()` - Model listing
- `get_model_info()` - Model metadata
- Provider caching mechanism
- Environment variable API key resolution

## Running Tests

### Run all provider tests:
```bash
pytest tests/providers/
```

### Run specific test file:
```bash
pytest tests/providers/test_openai_provider.py
```

### Run specific test class:
```bash
pytest tests/providers/test_openai_provider.py::TestOpenAIProvider
```

### Run specific test:
```bash
pytest tests/providers/test_openai_provider.py::TestOpenAIProvider::test_create_message_success
```

### Run with verbose output:
```bash
pytest tests/providers/ -v
```

### Run with coverage:
```bash
pytest tests/providers/ --cov=pyagentforge.providers --cov-report=html
```

## Test Design Principles

### 1. No Real API Calls
All tests use mocks to avoid making actual API calls:
- `unittest.mock.patch` for mocking API clients
- `AsyncMock` for async methods
- MagicMock for response objects

### 2. Comprehensive Coverage
Tests cover:
- Happy path scenarios
- Error handling
- Edge cases
- Parameter variations
- Format conversions

### 3. Isolation
Each test is independent:
- Uses pytest fixtures
- Doesn't rely on external state
- Cleans up after itself

### 4. Documentation
Tests serve as documentation:
- Clear test names describing what's tested
- Docstrings explaining test purpose
- Example usage patterns

## Test Statistics

| File | Test Classes | Test Methods | Lines |
|------|--------------|--------------|-------|
| test_base_provider.py | 3 | 28 | ~480 |
| test_openai_provider.py | 2 | 23 | ~550 |
| test_anthropic_provider.py | 2 | 22 | ~470 |
| test_google_provider.py | 2 | 27 | ~590 |
| test_factory.py | 3 | 29 | ~500 |
| **Total** | **12** | **129** | **~2,590** |

## Common Patterns

### Mocking API Responses
```python
mock_response = MagicMock()
mock_response.choices = [MagicMock()]
mock_response.choices[0].message.content = "Test response"

with patch.object(
    provider.client.chat.completions,
    "create",
    new_callable=AsyncMock,
    return_value=mock_response,
):
    response = await provider.create_message(...)
```

### Testing Token Counting
```python
messages = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi"},
]
token_count = await provider.count_tokens(messages)
assert isinstance(token_count, int)
```

### Testing Format Conversion
```python
tools = [{"name": "read", "description": "Read file"}]
openai_tools = provider._convert_tools_to_openai(tools)
assert openai_tools[0]["type"] == "function"
```

## Integration Tests

Real API integration tests are marked with `@pytest.mark.skip` and require:
- Actual API keys in environment variables
- Manual enablement for testing

## Future Enhancements

Potential areas for additional testing:
- Retry logic for transient failures
- Rate limiting handling
- Timeout behavior
- Concurrent request handling
- Response caching
- Model-specific behavior variations

---
Generated: 2026-02-20
