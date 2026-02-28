# JSON Config Guide (main/)

This project now uses centralized JSON config files under `main/`.

Chinese version: `main/Docs/JSON_CONFIG_README.zh-CN.md`

## Files

- `main/llm_config.json`
  - Active runtime config (recommended place to edit).
- `main/default_llm_config.json`
  - Fallback defaults when active config is missing.
- `main/llm_config.template.json`
  - Full template with more provider/model examples.
- `main/llm_config_schema.json`
  - JSON Schema for structure validation.

## Config Path Resolution Order

LLM config is loaded in this order:

1. `LLM_CONFIG_PATH` (if set)
2. `main/llm_config.json`
3. `{current_working_directory}/llm_config.json` (compatibility)
4. `main/default_llm_config.json`
5. Package fallback: `pyagentforge/config/default_llm_config.json`

## Minimal Structure

```json
{
  "default_model": "claude-sonnet-4-20250514",
  "max_tokens": 4096,
  "temperature": 1.0,
  "providers": {},
  "models": {}
}
```

## Important Sections

- `default_model`: model id used by default.
- `max_tokens`: default output token limit.
- `temperature`: default sampling temperature.
- `providers`: provider-level settings (key, base_url, timeout, retries).
- `models`: model-level settings (provider, api_type, context, output tokens).

## API Key Behavior

Current runtime behavior is:

1. Try environment variable first (for model/provider).
2. If env is missing, read API key from JSON config.

Practical recommendation:

- Prefer `api_key_env` for production or shared environments.
- Use `api_key` in JSON only for local/private setup.

## Example: Env-based Key (recommended)

```json
{
  "providers": {
    "anthropic": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY"
    }
  }
}
```

## Example: Direct Key in JSON (local only)

```json
{
  "providers": {
    "anthropic": {
      "enabled": true,
      "api_key": "YOUR_KEY_HERE"
    }
  }
}
```

## Example: Local Ollama

```json
{
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434/v1"
    }
  },
  "models": {
    "llama3.1": {
      "id": "llama3.1",
      "name": "Llama 3.1",
      "provider": "ollama",
      "api_type": "openai-completions",
      "context_window": 128000
    }
  }
}
```

## Quick Check

After editing config, verify the configuration by starting the Service API:

```bash
cd main/Service
uvicorn Service.gateway.app:create_app --factory --reload --port 8000
```

If startup reaches provider authentication errors, config path is likely correct and runtime is using real provider calls.
