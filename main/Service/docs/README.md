# Service & pyagentforge — Package Docs

```
pyagentforge/  (v3.0.0, Python >=3.11)
  kernel/       AgentEngine  ContextManager  ToolRegistry
  providers/    AnthropicProvider  OpenAIProvider  GoogleProvider
  tools/        register_core_tools  BashTool  ReadTool  WriteTool  EditTool  ...
  plugin/       Plugin  PluginManager  PluginConfig
  config/       get_engine_settings

Service/        (v0.1.0, Python >=3.11)
  gateway/      create_app  routes
  services/     AgentService  ModelConfigService  LegacyRuntimeService
    proxy/      WorkspaceManager  SessionManager  AgentExecutor  AgentProxyService
  schemas/      Pydantic request/response models
  config/       get_settings
  core/         ServiceRegistry
```

`service` depends on `pyagentforge>=3.0.0`.

```shell
pip install -e "main/agentforge-engine[dev]"
pip install -e "main/Service[dev]"
```

```python
from pyagentforge import create_minimal_engine, AnthropicProvider
from Service.gateway.app import create_app

engine = create_minimal_engine(
    provider=AnthropicProvider(api_key="sk-ant-...", model="claude-3-5-sonnet-20241022"),
    working_dir="/workspace",
)
app = create_app()
```

## Docs Index

```
00-common/package-conventions.md   import rules, naming, ruff config
00-common/configuration.md         LLM config, providers, model registry
01-install/installation.md         install steps, env vars, common errors
02-tools/tools.md                  ToolRegistry, built-in tools, BaseTool
03-agents/agents.md                AgentEngine, AgentConfig, AgentService, ModelConfigService
04-plans/plans.md                  PlanCreate, StepCreate, plan operations
05-proxy/workspaces.md             WorkspaceManager, WorkspaceContext, PermissionBridge
05-proxy/sessions.md               SessionManager, SessionResponse, LegacyRuntimeService
05-proxy/execution.md              AgentExecutor, AgentProxyService, stream events
99-reference/package-reference.md  full symbol speed reference
API_FULL.md                        everything in one file
```
