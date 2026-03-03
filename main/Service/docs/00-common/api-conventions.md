# Package Conventions

## Import Rule

```python
from pyagentforge import AgentEngine, create_provider, ToolRegistry  # always root import
# from pyagentforge.kernel.engine import AgentEngine                 # never submodule
```

Top-level only — no lazy imports inside functions.

## Naming

```
module / function   snake_case        register_core_tools  get_registry
class               PascalCase        AgentEngine          ModelConfig
constant            UPPER_SNAKE_CASE  BUILTIN_MODEL_IDS
type alias          PascalCase        ProviderType
```

## Type Annotations

All new/changed code must carry type hints:

```python
from pyagentforge import AgentEngine, BaseProvider, ToolRegistry

class AgentExecutor:
    _provider: BaseProvider | None = None
    _engine:   AgentEngine  | None = None
    _registry: ToolRegistry | None = None
```

## Ruff (pyproject.toml)

```toml
[tool.ruff]
target-version = "py311"
line-length    = 100
select  = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
ignore  = ["E501", "B008", "B905", "ARG001"]

[tool.ruff.isort]
known-first-party = ["Service", "pyagentforge"]
```

```shell
ruff check .   # in main/Service or main/agentforge-engine
ruff format .
```
