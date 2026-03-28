# Installation & Dev Setup

## Install

```shell
# Python >=3.11 required
pip install -e "main/agentforge-engine[dev]"
pip install -e "main/Service[dev]"
```

Verify:

```python
import pyagentforge; print(pyagentforge.__version__)   # 3.0.0
from pyagentforge import LLMClient, BashTool
from Service.gateway.app import create_app
```

## Configure

`main/llm_config.json` (gitignored):

```json
{
  "default_model": "default",
  "models": {
    "default": {
      "id": "default",
      "name": "Default Model",
      "provider": "openai-compatible",
      "api_type": "openai-completions",
      "model_name": "gpt-4o-mini",
      "base_url": "https://api.example.com/v1",
      "api_key_env": "LLM_API_KEY"
    }
  }
}
```

Or env vars:

```shell
$env:LLM_API_KEY = "sk-..."
```

## Start Service

```shell
cd main/Service
uvicorn Service.gateway.app:create_app --factory --reload --port 8000
```

## Test

```shell
cd main/agentforge-engine && pytest -v --tb=short
cd main/Service         && pytest tests/ -v --tb=short --cov=Service
```

## Common Errors

```
ImportError: No module named 'pyagentforge'
→  pip install -e "main/agentforge-engine[dev]"

401 Unauthorized from model endpoint
→  check main/llm_config.json and ensure api_key/api_key_env is valid

python version mismatch
→  python --version must be 3.11+
```
