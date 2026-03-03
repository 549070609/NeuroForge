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
from pyagentforge import AgentEngine, create_provider, BashTool
from Service.gateway.app import create_app
```

## Configure

`main/llm_config.json` (gitignored):

```json
{
  "default_model": "claude-3-5-sonnet-20241022",
  "providers": { "anthropic": { "api_key": "sk-ant-..." } }
}
```

Or env vars:

```shell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:OPENAI_API_KEY    = "sk-..."
$env:GOOGLE_API_KEY    = "AIza..."
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

AttributeError: 'Settings' object has no attribute 'anthropic_api_key'
→  configure main/llm_config.json or set ANTHROPIC_API_KEY

python version mismatch
→  python --version must be 3.11+
```
