# Package API Quick Reference

## pyagentforge — All Exports

```python
from pyagentforge import (
    # engine
    AgentEngine, AgentConfig, ContextManager, ToolExecutor, ToolRegistry,
    BaseTool, BaseProvider,
    Message, TextBlock, ToolUseBlock, ToolResultBlock, ProviderResponse,
    # providers
    create_provider, AnthropicProvider, OpenAIProvider, GoogleProvider,
    # tools
    register_core_tools,
    BashTool, ReadTool, WriteTool, EditTool, GlobTool, GrepTool,
    LsTool, WebFetchTool, WebSearchTool, TodoWriteTool, TodoReadTool,
    QuestionTool, ConfirmTool, PlanTool, PlanEnterTool, PlanExitTool,
    MultiEditTool, BatchTool, TaskTool, CodeSearchTool, ApplyPatchTool,
    DiffTool, LSPTool, WorkspaceTool, ExternalDirectoryTool,
    TruncationTool, ContextCompactTool, InvalidTool, ToolSuggestionTool,
    # model registry
    get_registry, register_model, register_provider, get_model,
    ModelRegistry, ModelConfig, ProviderType,
    # permission
    PermissionChecker,
    # chinese LLMs
    ChineseLLMRegistry,
    # config
    get_engine_settings,
    # plugin
    Plugin, PluginMetadata, PluginContext, PluginType,
    PluginManager, HookType, PluginConfig,
    # factory
    create_engine, create_minimal_engine,
)
```

## Service — Import Paths

```
Service.gateway.app                          create_app
Service.core.registry                        ServiceRegistry
Service.config                               get_settings
Service.services.agent_service               AgentService
Service.services.model_config_service        ModelConfigService
Service.services.legacy_runtime_service      LegacyRuntimeService
Service.services.proxy.agent_proxy_service   AgentProxyService
Service.services.proxy.workspace_manager     WorkspaceManager
Service.services.proxy.session_manager       SessionManager
Service.services.proxy.agent_executor        AgentExecutor  ExecutionResult
Service.services.proxy.permission_bridge     WorkspacePermissionChecker
                                             WorkspacePathValidator
                                             create_pyagentforge_permission_checker
Service.schemas                              ToolInfo  ExecuteToolRequest  ExecuteToolResponse
Service.schemas.proxy                        WorkspaceCreate  WorkspaceResponse
                                             SessionCreate  SessionResponse
                                             ProxyExecuteRequest  ProxyExecuteResponse
Service.schemas.models                       ModelConfigCreate  ModelConfigUpdate  ModelConfigResponse
Service.schemas.agents                       PlanCreate  PlanResponse  StepCreate
                                             StepUpdateRequest  StepAddRequest
                                             AgentExecuteRequest  AgentExecuteResponse
```

## Key Type Signatures

```python
create_provider(model_id: str, **kwargs) -> BaseProvider
create_minimal_engine(provider, working_dir=None) -> AgentEngine
create_engine(provider, config=None, plugin_config=None, working_dir=None) -> AgentEngine  # async
AgentEngine.run(prompt: str) -> str                                                          # async
AgentEngine.run_stream(prompt: str) -> AsyncGenerator[dict, None]

ToolRegistry.register(tool: BaseTool) -> None
ToolRegistry.get(name: str) -> BaseTool | None
ToolRegistry.get_all() -> dict[str, BaseTool]
ToolRegistry.filter_by_permission(allowed: list[str]) -> ToolRegistry
ToolRegistry.unregister(name: str) -> None

get_registry() -> ModelRegistry
register_model(config: ModelConfig) -> None
get_model(model_id: str) -> ModelConfig | None

WorkspaceManager.create_workspace(config: WorkspaceCreate) -> WorkspaceContext
WorkspaceManager.get_workspace(workspace_id: str) -> WorkspaceContext
SessionManager.create_session(workspace_id, agent_id, metadata={}) -> SessionResponse
AgentExecutor.initialize(agent_definition, system_prompt=None, config_overrides=None) -> None  # async
AgentExecutor.execute(prompt, context={}) -> ExecutionResult                                    # async
AgentExecutor.execute_stream(prompt, context={}) -> AsyncGenerator[dict, None]
AgentProxyService.execute(session_id, prompt, context=None, config_overrides=None) -> ProxyExecuteResponse  # async
```
