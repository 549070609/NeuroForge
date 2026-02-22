"""
Tests for Google Provider

Tests the Google Generative AI provider implementation with mocked API responses.
"""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from pyagentforge.providers.google_provider import GoogleProvider
from pyagentforge.core.message import ProviderResponse, TextBlock, ToolUseBlock


class TestGoogleProvider:
    """Test suite for Google Provider."""

    def test_google_provider_initialization(self):
        """Test Google provider initializes correctly."""
        provider = GoogleProvider(
            api_key="test-api-key",
            model="gemini-2.0-flash",
            max_tokens=8192,
            temperature=0.7,
        )

        assert provider.model == "gemini-2.0-flash"
        assert provider.max_tokens == 8192
        assert provider.temperature == 0.7
        assert provider.api_key == "test-api-key"
        assert provider._client is None  # Lazy initialization
        assert provider._model_instance is None

    def test_google_provider_default_model(self):
        """Test Google provider with default model."""
        provider = GoogleProvider(api_key="test-key")

        assert provider.model == "gemini-2.0-flash"

    def test_get_client_with_api_key(self):
        """Test client initialization with explicit API key."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        with patch("pyagentforge.providers.google_provider.google.generativeai") as mock_genai:
            client = provider._get_client()

            # Should configure with provided API key
            mock_genai.configure.assert_called_once_with(api_key="test-key")
            assert client == mock_genai

    def test_get_client_with_env_var(self):
        """Test client initialization with environment variable."""
        import os

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "env-key"}):
            provider = GoogleProvider(api_key=None, model="gemini-2.0-flash")

            with patch("pyagentforge.providers.google_provider.google.generativeai") as mock_genai:
                client = provider._get_client()

                mock_genai.configure.assert_called_once_with(api_key="env-key")

    def test_get_client_missing_api_key(self):
        """Test that missing API key raises error."""
        import os

        # Clear environment variable
        with patch.dict(os.environ, {}, clear=True):
            provider = GoogleProvider(api_key=None, model="gemini-2.0-flash")

            with pytest.raises(ValueError, match="Google API Key not provided"):
                provider._get_client()

    def test_get_client_import_error(self):
        """Test handling of missing google-generativeai package."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        with patch.dict(
            "sys.modules",
            {"google.generativeai": None, "google": None}
        ):
            with patch("pyagentforge.providers.google_provider.google.generativeai", side_effect=ImportError):
                with pytest.raises(ImportError, match="google-generativeai package not installed"):
                    provider._get_client()

    def test_convert_messages_simple(self):
        """Test simple message conversion to Google format."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        contents = provider._convert_messages(messages, system="You are helpful.")

        # Should have system prompt + model response + user message + assistant message
        assert len(contents) == 4
        assert contents[0]["role"] == "user"
        assert "System:" in contents[0]["parts"][0]["text"]
        assert contents[1]["role"] == "model"  # Model acknowledgment
        assert contents[2]["role"] == "user"
        assert contents[2]["parts"][0]["text"] == "Hello!"
        assert contents[3]["role"] == "model"
        assert contents[3]["parts"][0]["text"] == "Hi there!"

    def test_convert_messages_with_tool_use(self):
        """Test message conversion with tool use blocks."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me search for that."},
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "search",
                        "input": {"query": "test"},
                    },
                ],
            }
        ]

        contents = provider._convert_messages(messages, system="")

        # Should convert tool_use to function_call
        assert len(contents) >= 1
        assistant_msg = [c for c in contents if c["role"] == "model"][0]
        assert any("function_call" in part for part in assistant_msg["parts"])

    def test_convert_tools_to_google_format(self):
        """Test tool conversion to Google FunctionDeclaration format."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to file"},
                        },
                        "required": ["file_path"],
                    },
                },
            }
        ]

        declarations = provider._convert_tools(tools)

        assert declarations is not None
        assert len(declarations) == 1
        assert "function_declarations" in declarations[0]
        assert declarations[0]["function_declarations"][0]["name"] == "read_file"
        assert declarations[0]["function_declarations"][0]["description"] == "Read a file"

    def test_convert_tools_empty_list(self):
        """Test tool conversion with empty list."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        result = provider._convert_tools([])

        assert result is None

    @pytest.mark.asyncio
    async def test_create_message_success(self):
        """Test successful message creation."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        # Mock response
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.candidates[0].content.parts[0].text = "Hello! I'm Gemini."
        mock_response.candidates[0].content.parts[0].function_call = None
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        mock_response.usage_metadata.total_token_count = 30

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_model", return_value=mock_model):
            response = await provider.create_message(
                system="You are a helpful assistant.",
                messages=[{"role": "user", "content": "Hello!"}],
                tools=[],
            )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) == 1
        assert isinstance(response.content[0], TextBlock)
        assert response.content[0].text == "Hello! I'm Gemini."
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20

    @pytest.mark.asyncio
    async def test_create_message_with_tool_call(self):
        """Test message creation with function call."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        # Mock response with function call
        mock_function_call = MagicMock()
        mock_function_call.name = "search"
        mock_function_call.args = {"query": "test"}

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.candidates[0].content.parts[0].text = None
        mock_response.candidates[0].content.parts[0].function_call = mock_function_call
        mock_response.usage_metadata.prompt_token_count = 15
        mock_response.usage_metadata.candidates_token_count = 10
        mock_response.usage_metadata.total_token_count = 25

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_model", return_value=mock_model):
            response = await provider.create_message(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Search for test"}],
                tools=[{"type": "function", "function": {"name": "search", "description": "Search"}}],
            )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) == 1
        assert isinstance(response.content[0], ToolUseBlock)
        assert response.content[0].name == "search"
        assert response.content[0].input == {"query": "test"}
        assert response.stop_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_create_message_with_text_and_tool(self):
        """Test message creation with both text and function call."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        mock_function_call = MagicMock()
        mock_function_call.name = "read"
        mock_function_call.args = {"file": "test.txt"}

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [
            MagicMock(text="Let me read that file.", function_call=None),
            MagicMock(text=None, function_call=mock_function_call),
        ]
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = 30
        mock_response.usage_metadata.total_token_count = 50

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_model", return_value=mock_model):
            response = await provider.create_message(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Read the file"}],
                tools=[],
            )

        assert len(response.content) == 2
        assert isinstance(response.content[0], TextBlock)
        assert isinstance(response.content[1], ToolUseBlock)
        assert response.has_tool_calls is True

    @pytest.mark.asyncio
    async def test_create_message_api_error(self):
        """Test handling of API errors."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(
            side_effect=Exception("API Error")
        )

        with patch.object(provider, "_get_model", return_value=mock_model):
            with pytest.raises(Exception, match="API Error"):
                await provider.create_message(
                    system="System",
                    messages=[{"role": "user", "content": "Test"}],
                    tools=[],
                )

    @pytest.mark.asyncio
    async def test_count_tokens_with_model(self):
        """Test token counting using model's count_tokens."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        mock_result = MagicMock()
        mock_result.total_tokens = 42

        mock_model = MagicMock()
        mock_model.count_tokens = MagicMock(return_value=mock_result)

        with patch.object(provider, "_get_model", return_value=mock_model):
            messages = [{"role": "user", "content": "Test message"}]
            token_count = await provider.count_tokens(messages)

        assert token_count == 42

    @pytest.mark.asyncio
    async def test_count_tokens_fallback(self):
        """Test token counting fallback estimation."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        mock_model = MagicMock()
        mock_model.count_tokens = MagicMock(side_effect=Exception("Count failed"))

        with patch.object(provider, "_get_model", return_value=mock_model):
            messages = [{"role": "user", "content": "Test message here"}]
            token_count = await provider.count_tokens(messages)

        # Should fallback to length // 4
        assert token_count == len("Test message here") // 4

    @pytest.mark.asyncio
    async def test_stream_message_yields_chunks(self):
        """Test that stream_message yields text deltas."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        # Mock streaming response
        async def mock_stream():
            chunks = [
                MagicMock(text="Hello"),
                MagicMock(text=" world"),
                MagicMock(text="!"),
            ]
            for chunk in chunks:
                yield chunk

        mock_response_stream = mock_stream()

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response_stream)

        with patch.object(provider, "_get_model", return_value=mock_model):
            chunks = []
            async for chunk in provider.stream_message(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
            ):
                chunks.append(chunk)

        # Should have received text deltas plus final response
        text_deltas = [c for c in chunks if isinstance(c, dict) and c.get("type") == "text_delta"]
        assert len(text_deltas) >= 3

    @pytest.mark.asyncio
    async def test_stream_message_with_tools(self):
        """Test streaming with tools."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        async def mock_stream():
            yield MagicMock(text="Processing")

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_stream())

        with patch.object(provider, "_get_model", return_value=mock_model):
            chunks = []
            async for chunk in provider.stream_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[{"type": "function", "function": {"name": "test", "description": "Test"}}],
            ):
                chunks.append(chunk)

        assert len(chunks) > 0

    def test_convert_schema(self):
        """Test JSON Schema conversion to Google format."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
            "description": "Person schema",
        }

        result = provider._convert_schema(schema)

        assert result["type"] == "object"
        assert "properties" in result
        assert "required" in result
        assert result["description"] == "Person schema"

    def test_parse_response_empty_candidates(self):
        """Test parsing response with no candidates."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        mock_response = MagicMock()
        mock_response.candidates = []

        result = provider._parse_response(mock_response)

        # Should return empty text response
        assert isinstance(result, ProviderResponse)
        assert len(result.content) == 1
        assert result.text == ""

    def test_parse_response_with_usage(self):
        """Test parsing response usage metadata."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock(text="Response")]
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150

        result = provider._parse_response(mock_response)

        assert result.usage["input_tokens"] == 100
        assert result.usage["output_tokens"] == 50
        assert result.usage["total_tokens"] == 150

    def test_different_gemini_models(self):
        """Test provider with different Gemini models."""
        models = [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]

        for model in models:
            provider = GoogleProvider(api_key="test-key", model=model)
            assert provider.model == model

    @pytest.mark.asyncio
    async def test_create_message_with_extra_params(self):
        """Test that extra params are passed through."""
        provider = GoogleProvider(
            api_key="test-key",
            model="gemini-2.0-flash",
            max_tokens=4096,
            temperature=0.8,
            custom_param="value",
        )

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock(text="Response")]
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        mock_response.usage_metadata.total_token_count = 30

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_model", return_value=mock_model):
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
            )

        # Extra params should be in provider instance
        assert provider.extra_params == {"custom_param": "value"}

    @pytest.mark.asyncio
    async def test_message_conversion_preserves_role(self):
        """Test that message roles are correctly converted."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        messages = [
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant message"},
        ]

        contents = provider._convert_messages(messages, system="")

        # Filter out system prompt exchange
        user_msgs = [c for c in contents if c["role"] == "user" and "System:" not in c["parts"][0].get("text", "")]
        model_msgs = [c for c in contents if c["role"] == "model"]

        assert len(user_msgs) == 1
        assert user_msgs[0]["parts"][0]["text"] == "User message"
        assert len(model_msgs) == 1

    @pytest.mark.asyncio
    async def test_lazy_client_initialization(self):
        """Test that client is lazily initialized."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        assert provider._client is None

        with patch("pyagentforge.providers.google_provider.google.generativeai") as mock_genai:
            client = provider._get_client()
            assert provider._client is not None
            assert client == mock_genai

            # Second call should return cached client
            client2 = provider._get_client()
            assert client == client2

    @pytest.mark.asyncio
    async def test_lazy_model_initialization(self):
        """Test that model is lazily initialized."""
        provider = GoogleProvider(api_key="test-key", model="gemini-2.0-flash")

        assert provider._model_instance is None

        with patch("pyagentforge.providers.google_provider.google.generativeai") as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel = MagicMock(return_value=mock_model)

            model = provider._get_model()

            assert provider._model_instance is not None
            assert model == mock_model

            # Second call should return cached model
            model2 = provider._get_model()
            assert model == model2


class TestGoogleProviderIntegration:
    """Integration tests that require actual API calls (skip in CI)."""

    @pytest.mark.skip(reason="Requires actual API key")
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """Test with real Google API (requires API key in environment)."""
        import os

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            pytest.skip("GOOGLE_API_KEY not set")

        provider = GoogleProvider(api_key=api_key, model="gemini-2.0-flash")

        response = await provider.create_message(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Say 'test'"}],
            tools=[],
        )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) > 0
