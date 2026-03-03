"""
Tests for Provider Factory

Tests the ModelAdapterFactory for creating provider instances based on model configuration.
"""

import os
import pytest
from typing import Any
from unittest.mock import MagicMock, patch

from pyagentforge.providers.factory import (
    ModelAdapterFactory,
    create_provider,
    create_provider_from_config,
    get_factory,
    get_supported_models,
)
from pyagentforge.providers.openai_provider import OpenAIProvider
from pyagentforge.providers.anthropic_provider import AnthropicProvider
from pyagentforge.providers.google_provider import GoogleProvider
from pyagentforge.providers.base import BaseProvider
from pyagentforge.kernel.model_registry import (
    ModelConfig,
    ModelRegistry,
    ProviderType,
)


class TestModelAdapterFactory:
    """Test suite for ModelAdapterFactory."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock model registry with test models."""
        registry = MagicMock(spec=ModelRegistry)

        # Configure test models
        test_models = {
            "gpt-4-turbo": ModelConfig(
                id="gpt-4-turbo",
                name="GPT-4 Turbo",
                provider=ProviderType.OPENAI,
                api_type="openai-completions",
                api_key_env="OPENAI_API_KEY",
                context_window=128000,
                max_output_tokens=4096,
                supports_vision=True,
                supports_tools=True,
                supports_streaming=True,
            ),
            "claude-sonnet-4-20250514": ModelConfig(
                id="claude-sonnet-4-20250514",
                name="Claude Sonnet 4",
                provider=ProviderType.ANTHROPIC,
                api_type="anthropic-messages",
                api_key_env="ANTHROPIC_API_KEY",
                context_window=200000,
                max_output_tokens=8192,
                supports_vision=True,
                supports_tools=True,
                supports_streaming=True,
            ),
            "gemini-2.0-flash": ModelConfig(
                id="gemini-2.0-flash",
                name="Gemini 2.0 Flash",
                provider=ProviderType.GOOGLE,
                api_type="google-generative-ai",
                api_key_env="GOOGLE_API_KEY",
                context_window=1000000,
                max_output_tokens=8192,
                supports_vision=True,
                supports_tools=True,
                supports_streaming=True,
            ),
        }

        registry.get_model = MagicMock(side_effect=lambda mid: test_models.get(mid))
        registry.get_all_models = MagicMock(return_value=list(test_models.values()))

        return registry

    def test_factory_initialization(self, mock_registry):
        """Test factory initializes correctly."""
        factory = ModelAdapterFactory(registry=mock_registry)

        assert factory.registry == mock_registry
        assert factory._provider_cache == {}

    def test_factory_default_registry(self):
        """Test factory uses global registry by default."""
        factory = ModelAdapterFactory()

        assert factory.registry is not None

    def test_create_openai_provider(self, mock_registry):
        """Test creating OpenAI provider."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider("gpt-4-turbo")

        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4-turbo"

    def test_create_anthropic_provider(self, mock_registry):
        """Test creating Anthropic provider."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider("claude-sonnet-4-20250514")

        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "claude-sonnet-4-20250514"

    def test_create_google_provider(self, mock_registry):
        """Test creating Google provider."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider("gemini-2.0-flash")

        assert isinstance(provider, GoogleProvider)
        assert provider.model == "gemini-2.0-flash"

    def test_unknown_provider_raises_error(self, mock_registry):
        """Test that unknown provider type raises error."""
        mock_model = ModelConfig.model_construct(
            id="unknown-model",
            name="Unknown Model",
            provider="unsupported_provider",
            api_type="custom",
            context_window=1000,
            max_output_tokens=100,
        )
        mock_registry.get_model = MagicMock(return_value=mock_model)

        factory = ModelAdapterFactory(registry=mock_registry)

        with pytest.raises((ValueError, KeyError)):
            factory.create_provider("unknown-model")

    def test_unknown_model_raises_error(self, mock_registry):
        """Test that unknown model ID raises error."""
        mock_registry.get_model = MagicMock(return_value=None)

        factory = ModelAdapterFactory(registry=mock_registry)

        with pytest.raises(ValueError, match="Model not found"):
            factory.create_provider("nonexistent-model")

    def test_provider_caching(self, mock_registry):
        """Test that providers are cached."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)

            provider1 = factory.create_provider("gpt-4-turbo")
            provider2 = factory.create_provider("gpt-4-turbo")

        # Should return same cached instance
        assert provider1 is provider2

    def test_provider_cache_with_different_kwargs(self, mock_registry):
        """Test that different kwargs create different cached providers."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)

            provider1 = factory.create_provider("gpt-4-turbo", temperature=0.5)
            provider2 = factory.create_provider("gpt-4-turbo", temperature=0.9)

        # Should be different instances due to different kwargs
        assert provider1 is not provider2
        assert provider1.temperature == 0.5
        assert provider2.temperature == 0.9

    def test_create_provider_with_custom_max_tokens(self, mock_registry):
        """Test creating provider with custom max_tokens."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider("gpt-4-turbo", max_tokens=2048)

        assert provider.max_tokens == 2048

    def test_create_provider_with_custom_temperature(self, mock_registry):
        """Test creating provider with custom temperature."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider("claude-sonnet-4-20250514", temperature=0.7)

        assert provider.temperature == 0.7

    def test_create_openai_provider_with_base_url(self, mock_registry):
        """Test creating OpenAI provider with custom base_url."""
        mock_model = ModelConfig(
            id="custom-gpt",
            name="Custom GPT",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="OPENAI_API_KEY",
            base_url="https://custom.api.com/v1",
            context_window=100000,
            max_output_tokens=4096,
        )
        mock_registry.get_model = MagicMock(return_value=mock_model)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider("custom-gpt")

        assert str(provider.client.base_url).rstrip("/") == "https://custom.api.com/v1"

    def test_get_supported_models(self, mock_registry):
        """Test getting list of supported models."""
        factory = ModelAdapterFactory(registry=mock_registry)
        models = factory.get_supported_models()

        assert len(models) == 3
        assert "gpt-4-turbo" in models
        assert "claude-sonnet-4-20250514" in models
        assert "gemini-2.0-flash" in models

    def test_get_model_info(self, mock_registry):
        """Test getting model information."""
        factory = ModelAdapterFactory(registry=mock_registry)
        info = factory.get_model_info("gpt-4-turbo")

        assert info is not None
        assert info["id"] == "gpt-4-turbo"
        assert info["name"] == "GPT-4 Turbo"
        assert info["provider"] == "openai"
        assert info["context_window"] == 128000
        assert info["supports_vision"] is True

    def test_get_model_info_unknown_model(self, mock_registry):
        """Test getting info for unknown model."""
        mock_registry.get_model = MagicMock(return_value=None)

        factory = ModelAdapterFactory(registry=mock_registry)
        info = factory.get_model_info("nonexistent")

        assert info is None

    def test_create_azure_provider_import_error(self, mock_registry):
        """Test Azure provider raises helpful error when not implemented."""
        mock_model = ModelConfig(
            id="azure-gpt",
            name="Azure GPT",
            provider=ProviderType.AZURE,
            api_type="custom",
            api_key_env="AZURE_API_KEY",
            base_url="https://azure.endpoint.com",
            context_window=100000,
            max_output_tokens=4096,
        )
        mock_registry.get_model = MagicMock(return_value=mock_model)

        factory = ModelAdapterFactory(registry=mock_registry)

        with pytest.raises(ImportError, match="Azure Provider not implemented"):
            factory.create_provider("azure-gpt")

    def test_create_bedrock_provider_import_error(self, mock_registry):
        """Test Bedrock provider raises helpful error when not implemented."""
        mock_model = ModelConfig(
            id="bedrock-claude",
            name="Bedrock Claude",
            provider=ProviderType.BEDROCK,
            api_type="bedrock-converse-stream",
            context_window=100000,
            max_output_tokens=4096,
        )
        mock_registry.get_model = MagicMock(return_value=mock_model)

        factory = ModelAdapterFactory(registry=mock_registry)

        with pytest.raises(ImportError, match="Bedrock Provider not implemented"):
            factory.create_provider("bedrock-claude")

    def test_create_custom_provider_not_registered(self, mock_registry):
        """Test custom provider raises error when factory not registered."""
        mock_model = ModelConfig(
            id="custom-model",
            name="Custom Model",
            provider=ProviderType.CUSTOM,
            api_type="custom",
            context_window=100000,
            max_output_tokens=4096,
        )
        mock_registry.get_model = MagicMock(return_value=mock_model)
        mock_registry.get_provider = MagicMock(return_value=None)

        factory = ModelAdapterFactory(registry=mock_registry)

        with pytest.raises(ValueError, match="Custom provider.*not registered"):
            factory.create_provider("custom-model")

    def test_create_custom_provider_with_factory(self, mock_registry):
        """Test creating custom provider with registered factory."""
        mock_model = ModelConfig(
            id="custom-model",
            name="Custom Model",
            provider=ProviderType.CUSTOM,
            api_type="custom",
            context_window=100000,
            max_output_tokens=4096,
        )

        # Mock custom provider
        class CustomProvider(BaseProvider):
            async def create_message(self, system, messages, tools, **kwargs):
                from pyagentforge.kernel.message import ProviderResponse, TextBlock
                return ProviderResponse(content=[TextBlock(text="test")], stop_reason="end_turn")

            async def count_tokens(self, messages):
                return 0

        mock_provider_info = MagicMock()
        mock_provider_info.is_registered = True
        mock_provider_info.factory = MagicMock(return_value=CustomProvider(model="custom-model"))

        mock_registry.get_model = MagicMock(return_value=mock_model)
        mock_registry.get_provider = MagicMock(return_value=mock_provider_info)

        factory = ModelAdapterFactory(registry=mock_registry)
        provider = factory.create_provider("custom-model")

        assert isinstance(provider, CustomProvider)

    def test_convenience_function_create_provider(self, mock_registry):
        """Test the convenience create_provider function."""
        with patch("pyagentforge.providers.factory.get_factory") as mock_get_factory:
            mock_factory = MagicMock()
            mock_get_factory.return_value = mock_factory

            create_provider("gpt-4", temperature=0.7)

            mock_factory.create_provider.assert_called_once_with(
                "gpt-4", temperature=0.7
            )

    def test_convenience_function_get_supported_models(self, mock_registry):
        """Test the convenience get_supported_models function."""
        with patch("pyagentforge.providers.factory.get_factory") as mock_get_factory:
            mock_factory = MagicMock()
            mock_factory.get_supported_models.return_value = ["model1", "model2"]
            mock_get_factory.return_value = mock_factory

            models = get_supported_models()

            assert models == ["model1", "model2"]

    def test_get_factory_singleton(self):
        """Test that get_factory returns singleton instance."""
        factory1 = get_factory()
        factory2 = get_factory()

        assert factory1 is factory2

    def test_model_config_extra_params_passed_to_provider(self, mock_registry):
        """Test that extra params from model config are passed to provider."""
        mock_model = ModelConfig(
            id="test-model",
            name="Test Model",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="OPENAI_API_KEY",
            context_window=100000,
            max_output_tokens=4096,
            extra={"custom_param": "value", "another": 42},
        )
        mock_registry.get_model = MagicMock(return_value=mock_model)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider("test-model")

        assert provider.extra_params == {"custom_param": "value", "another": 42}

    def test_provider_creation_logs_info(self, mock_registry):
        """Test that provider creation is logged."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("pyagentforge.providers.factory.logger") as mock_logger:
                factory = ModelAdapterFactory(registry=mock_registry)
                factory.create_provider("gpt-4-turbo")

                # Should log provider creation
                mock_logger.info.assert_called()


class TestProviderFactoryEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock model registry with test models."""
        registry = MagicMock(spec=ModelRegistry)

        test_models = {
            "gpt-4-turbo": ModelConfig(
                id="gpt-4-turbo",
                name="GPT-4 Turbo",
                provider=ProviderType.OPENAI,
                api_type="openai-completions",
                api_key_env="OPENAI_API_KEY",
                context_window=128000,
                max_output_tokens=4096,
            ),
        }
        registry.get_model = MagicMock(side_effect=lambda mid: test_models.get(mid))
        registry.get_all_models = MagicMock(return_value=list(test_models.values()))
        return registry

    def test_factory_with_none_registry(self):
        """Test factory handles None registry by using default."""
        factory = ModelAdapterFactory(registry=None)

        assert factory.registry is not None

    def test_cache_key_includes_all_kwargs(self):
        """Test that cache key considers all kwargs."""
        registry = MagicMock(spec=ModelRegistry)

        mock_model = ModelConfig(
            id="test-model",
            name="Test",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="TEST_KEY",
            context_window=1000,
            max_output_tokens=100,
        )
        registry.get_model = MagicMock(return_value=mock_model)

        with patch.dict(os.environ, {"TEST_KEY": "key"}):
            factory = ModelAdapterFactory(registry=registry)

            # Create providers with different kwargs
            p1 = factory.create_provider("test-model", param1="a", param2="b")
            p2 = factory.create_provider("test-model", param1="a", param2="c")
            p3 = factory.create_provider("test-model", param1="a", param2="b")

            # p1 and p3 should be same (identical kwargs)
            # p2 should be different
            assert p1 is p3
            assert p1 is not p2

    def test_model_config_cost_info(self, mock_registry):
        """Test that model cost info is available."""
        factory = ModelAdapterFactory(registry=mock_registry)
        info = factory.get_model_info("gpt-4-turbo")

        # Cost info should be present (even if 0)
        assert "cost_input" in info or hasattr(mock_registry.get_model("gpt-4-turbo"), "cost_input")

    def test_missing_api_key_env_var(self, mock_registry):
        """Test that missing API key raises an error from the provider SDK."""
        with patch.dict(os.environ, {}, clear=True):
            factory = ModelAdapterFactory(registry=mock_registry)
            with pytest.raises(Exception):
                factory.create_provider("gpt-4-turbo")


class TestCreateProviderFromConfig:
    """Tests for the create_provider_from_config() method and convenience function."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock model registry."""
        return MagicMock(spec=ModelRegistry)

    def test_create_provider_from_config_anthropic(self, mock_registry):
        """Test creating Anthropic provider from explicit ModelConfig."""
        config = ModelConfig(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            provider=ProviderType.ANTHROPIC,
            api_type="anthropic-messages",
            api_key_env="ANTHROPIC_API_KEY",
            context_window=200000,
            max_output_tokens=8192,
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider_from_config(config)

        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "claude-sonnet-4-20250514"

    def test_create_provider_from_config_openai(self, mock_registry):
        """Test creating OpenAI provider from explicit ModelConfig."""
        config = ModelConfig(
            id="gpt-4o",
            name="GPT-4o",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="OPENAI_API_KEY",
            context_window=128000,
            max_output_tokens=4096,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider_from_config(config, temperature=0.5)

        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o"
        assert provider.temperature == 0.5

    def test_create_provider_from_config_with_kwargs(self, mock_registry):
        """Test that extra kwargs are forwarded correctly."""
        config = ModelConfig(
            id="gpt-4o",
            name="GPT-4o",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="OPENAI_API_KEY",
            context_window=128000,
            max_output_tokens=4096,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            provider = factory.create_provider_from_config(
                config, max_tokens=2048, temperature=0.3
            )

        assert provider.max_tokens == 2048
        assert provider.temperature == 0.3

    def test_create_provider_from_config_skips_registry_lookup(self, mock_registry):
        """Verify that create_provider_from_config does NOT call registry.get_model()."""
        config = ModelConfig(
            id="gpt-4o",
            name="GPT-4o",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="OPENAI_API_KEY",
            context_window=128000,
            max_output_tokens=4096,
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            factory.create_provider_from_config(config)

        mock_registry.get_model.assert_not_called()

    def test_convenience_function_create_provider_from_config(self):
        """Test the module-level create_provider_from_config function."""
        config = ModelConfig(
            id="gpt-4o",
            name="GPT-4o",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="OPENAI_API_KEY",
            context_window=128000,
            max_output_tokens=4096,
        )

        with patch("pyagentforge.providers.factory.get_factory") as mock_get_factory:
            mock_factory = MagicMock()
            mock_get_factory.return_value = mock_factory

            create_provider_from_config(config, temperature=0.7)

            mock_factory.create_provider_from_config.assert_called_once_with(
                config, temperature=0.7
            )

    def test_legacy_create_provider_emits_deprecation_warning(self, mock_registry):
        """Test that the legacy create_provider() emits DeprecationWarning."""
        with patch("pyagentforge.providers.factory.get_factory") as mock_get_factory:
            mock_factory = MagicMock()
            mock_get_factory.return_value = mock_factory

            with pytest.warns(DeprecationWarning, match="create_provider_from_config"):
                create_provider("gpt-4")

    def test_from_config_equivalent_to_old_path(self, mock_registry):
        """Provider from create_provider_from_config matches create_provider behavior."""
        config = ModelConfig(
            id="gpt-4-turbo",
            name="GPT-4 Turbo",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            api_key_env="OPENAI_API_KEY",
            context_window=128000,
            max_output_tokens=4096,
        )
        mock_registry.get_model = MagicMock(return_value=config)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=mock_registry)
            p_old = factory.create_provider("gpt-4-turbo", temperature=0.5)
            p_new = factory.create_provider_from_config(config, temperature=0.5)

        assert type(p_old) is type(p_new)
        assert p_old.model == p_new.model
        assert p_old.temperature == p_new.temperature


class TestProviderFactoryIntegration:
    """Integration tests for provider factory."""

    @pytest.mark.skip(reason="Requires actual registry setup")
    def test_real_registry_integration(self):
        """Test with real model registry."""
        factory = ModelAdapterFactory()

        models = factory.get_supported_models()
        assert len(models) > 0

        # Test that we can get info for common models
        for model_id in models[:5]:  # Check first 5 models
            info = factory.get_model_info(model_id)
            assert info is not None
            assert "id" in info
            assert "provider" in info
