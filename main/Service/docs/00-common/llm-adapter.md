# LLM Configuration

## Config Load Order

```
$LLM_CONFIG_PATH  →  main/llm_config.json  →  {cwd}/llm_config.json  →  main/default_llm_config.json
```

## Engine Settings

```python
from pyagentforge import get_engine_settings
s = get_engine_settings()
# s.default_model  s.anthropic_api_key  s.openai_api_key  s.google_api_key
```

## Provider

```python
from pyagentforge import create_provider, AnthropicProvider, OpenAIProvider, GoogleProvider

provider = create_provider("claude-3-5-sonnet-20241022", temperature=1.0, max_tokens=4096)
provider = AnthropicProvider(api_key="sk-ant-...", model="claude-3-5-sonnet-20241022")
provider = OpenAIProvider(api_key="sk-...",          model="gpt-4o")
provider = GoogleProvider(api_key="AIza...",         model="gemini-2.0-flash")
```

## Model Registry

```python
from pyagentforge import get_registry, register_model, get_model, ModelConfig, ProviderType

registry = get_registry()
registry.get_all_models() -> list[ModelConfig]
registry.get_model(model_id) -> ModelConfig | None

register_model(ModelConfig(
    id="custom-model",
    name="Custom",
    provider=ProviderType.ANTHROPIC,   # ANTHROPIC | OPENAI | GOOGLE | ZHIPU | ...
    api_type="anthropic",
    context_window=200000,
    supports_tools=True,
    supports_streaming=True,
))
get_model("custom-model") -> ModelConfig | None
```

## Chinese LLM Registry

```python
from pyagentforge import ChineseLLMRegistry

ChineseLLMRegistry.get_all_providers() -> dict[str, ProviderInfo]
ChineseLLMRegistry.get_provider("zhipu") -> ProviderInfo | None
# ProviderInfo: vendor  vendor_name  models  default_model  api_key_env  base_url  description
```

## Service Config

```python
from Service.config import get_settings
s = get_settings()
# s.legacy_sessions_dir  s.default_model  s.api_key
```

## Env Vars

```
ANTHROPIC_API_KEY    OpenAI_API_KEY    GOOGLE_API_KEY    GLM_API_KEY    LLM_CONFIG_PATH
SERVICE_API_KEY      SERVICE_LEGACY_SESSIONS_DIR          SERVICE_DEFAULT_MODEL
```

## llm_config.json Format

```json
{
  "default_model": "claude-3-5-sonnet-20241022",
  "providers": {
    "anthropic": { "api_key": "${ANTHROPIC_API_KEY}" },
    "openai":    { "api_key": "${OPENAI_API_KEY}" },
    "google":    { "api_key": "${GOOGLE_API_KEY}", "default_model": "gemini-2.0-flash" }
  }
}
```
