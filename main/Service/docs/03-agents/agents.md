# Agent Services

## AgentEngine

```python
from pyagentforge import create_minimal_engine, create_engine, AnthropicProvider

# no plugins
engine = create_minimal_engine(
    provider=AnthropicProvider(api_key="sk-ant-...", model="claude-3-5-sonnet-20241022"),
    working_dir="/workspace",
)
# with plugins
engine = await create_engine(provider, config={...}, plugin_config=PluginConfig(...))

result: str = await engine.run("task")

async for event in engine.run_stream("task"):
    # event["type"]: "stream" | "tool_start" | "tool_result" | "complete" | "error"
    match event.get("type"):
        case "stream":    print(event["event"]["delta"], end="")
        case "complete":  final = event["text"]
        case "error":     raise RuntimeError(event["message"])

engine.reset()
engine.get_context_summary() -> dict
engine.session_id -> str
```

## AgentConfig

```python
class AgentConfig:
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 1.0
    max_iterations: int = 100
    permission_checker: PermissionChecker | None = None
```

## AgentService

Auto-initialized by `create_app()`. Agent definitions loaded from `main/Agent/`.

```python
from Service.services.agent_service import AgentService

service.list_agents(namespace=None, tags=None) -> AgentListResponse
service.get_agent(agent_id) -> AgentInfoResponse    # raises KeyError if not found
service.refresh_directory()
service.execute_agent(agent_id, task, context={}) -> AgentExecuteResponse
```

```
AgentInfoResponse fields:
  id  name  namespace  origin  description  tags  category
  is_readonly  max_concurrent  tools  denied_tools
```

Agent definition YAML (`main/Agent/<name>/agent.yaml`):

```yaml
id: plan
name: Plan Agent
namespace: default
tags: [plan, code]
model:
  id: claude-3-5-sonnet-20241022
  temperature: 1.0
  max_tokens: 4096
limits:
  max_iterations: 50
capabilities:
  tools: ["read", "write", "bash", "glob", "grep"]
  denied_tools: []
```

## ModelConfigService

```python
from Service.services.model_config_service import ModelConfigService

service.list_models(provider=None, supports_vision=None, supports_tools=None) -> list[ModelConfigResponse]
service.get_model(model_id) -> ModelConfigResponse | None
service.create_model(ModelConfigCreate(...)) -> ModelConfigResponse
service.update_model(model_id, ModelConfigUpdate(...)) -> ModelConfigResponse
service.delete_model(model_id) -> bool    # raises ValueError for builtin IDs
service.get_stats() -> ModelConfigStatsResponse
service.list_chinese_providers() -> ChineseProviderListResponse
service.get_chinese_provider(vendor) -> ChineseProviderInfo | None
```

Builtin model IDs (delete-protected):
```
claude-sonnet-4-20250514  claude-3-5-sonnet-20241022  claude-3-5-haiku-20241022
claude-opus-4-20250514    gpt-4o  gpt-4o-mini  o1-preview  o3-mini
gemini-2.0-flash          glm-4-flash  glm-4-plus  glm-4-air  glm-4-airx  glm-4-long  glm-4.7  glm-5
```
