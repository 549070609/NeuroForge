# NeuroForge — Service & pyagentforge Package Reference

```shell
# requires Python >=3.11; install in order (service depends on pyagentforge)
pip install -e "main/agentforge-engine[dev]"
pip install -e "main/Service[dev]"
```

```
pyagentforge/  (v3.0.0)   kernel/ providers/ tools/builtin/ plugin/ config/
Service/       (v0.1.0)   gateway/ services/proxy/ schemas/ config/ core/
```

**Import rule**: always `from pyagentforge import <symbol>` — never from submodules.

---

## pyagentforge — Full Import Surface

```python
from pyagentforge import (
    # engine
    AgentEngine, AgentConfig, ContextManager, ToolExecutor, ToolRegistry,
    BaseTool, BaseProvider,
    # message types
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

---

## AgentEngine

```python
from pyagentforge import create_minimal_engine, create_engine, AnthropicProvider

# sync create, no plugins
engine = create_minimal_engine(
    provider=AnthropicProvider(api_key="sk-ant-...", model="claude-3-5-sonnet-20241022"),
    working_dir="/workspace",
)
# async create, with plugin config
engine = await create_engine(provider, config={...}, plugin_config=PluginConfig(...))

result: str = await engine.run("task description")

async for event in engine.run_stream("task"):
    # event["type"]: "stream" | "tool_start" | "tool_result" | "complete" | "error"
    match event.get("type"):
        case "stream":    print(event["event"]["delta"], end="")
        case "complete":  final = event["text"]
        case "error":     raise RuntimeError(event["message"])

engine.reset()                        # clear conversation context
engine.get_context_summary() -> dict
engine.session_id -> str
```

---

## AgentConfig

```python
class AgentConfig:
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 1.0
    max_iterations: int = 100
    permission_checker: PermissionChecker | None = None
```

---

## ToolRegistry

```python
registry = ToolRegistry()
register_core_tools(registry)                        # bash read write edit glob grep
register_core_tools(registry, working_dir="/path")   # scoped to directory

registry.register(WebFetchTool())
registry.get("bash") -> BaseTool | None
registry.get_all() -> dict[str, BaseTool]
len(registry) -> int
registry.filter_by_permission(["read", "write"]) -> ToolRegistry
registry.unregister("bash")
```

---

## Built-in Tools

```
tool_name       class                  description
─────────────────────────────────────────────────────────
bash            BashTool               execute shell command
read            ReadTool               read file contents
write           WriteTool              write file
edit            EditTool               string-replace edit file
glob            GlobTool               find files by pattern
grep            GrepTool               regex search in files
ls              LsTool                 list directory
web_fetch       WebFetchTool           fetch URL content
web_search      WebSearchTool          web search
todo_write      TodoWriteTool          write structured TODO list
todo_read       TodoReadTool           read TODO list
question        QuestionTool           multi-choice prompt to user
confirm         ConfirmTool            boolean confirmation from user
plan            PlanTool               plan management
plan_enter      PlanEnterTool          enter plan mode
plan_exit       PlanExitTool           exit plan mode
multi_edit      MultiEditTool          batch file edits
batch           BatchTool              parallel tool calls
task            TaskTool               launch sub-agent task
code_search     CodeSearchTool         semantic code search
apply_patch     ApplyPatchTool         apply unified diff
diff            DiffTool               generate file diff
lsp             LSPTool                language server protocol
workspace       WorkspaceTool          workspace operations
external_dir    ExternalDirectoryTool  access external directory
truncation      TruncationTool         context truncation
context_compact ContextCompactTool     context compression
```

---

## Custom BaseTool

```python
class MyTool(BaseTool):
    name = "my_tool"
    description = "one-line description"

    async def execute(self, param: str, count: int = 1) -> str:
        return f"result"

    def to_anthropic_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"},
                    "count": {"type": "integer", "default": 1},
                },
                "required": ["param"],
            },
        }
```

---

## Provider

```python
# factory — infers provider from model_id
provider = create_provider("claude-3-5-sonnet-20241022", temperature=1.0, max_tokens=4096)

# explicit
provider = AnthropicProvider(api_key="sk-ant-...", model="claude-3-5-sonnet-20241022")
provider = OpenAIProvider(api_key="sk-...",          model="gpt-4o")
provider = GoogleProvider(api_key="AIza...",         model="gemini-2.0-flash")
```

---

## ModelConfig & Registry

```python
class ModelConfig:
    id: str
    name: str
    provider: ProviderType          # ANTHROPIC | OPENAI | GOOGLE | ZHIPU | ...
    api_type: str
    supports_vision: bool = False
    supports_tools: bool = True
    supports_streaming: bool = True
    context_window: int = 200000
    max_output_tokens: int | None = None
    cost_input: float | None = None
    cost_output: float | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    extra: dict | None = None
```

```python
registry = get_registry()
registry.get_all_models() -> list[ModelConfig]
registry.get_model(model_id) -> ModelConfig | None

register_model(ModelConfig(id="my-model", provider=ProviderType.ANTHROPIC, ...))
get_model("my-model") -> ModelConfig | None

# Chinese LLM providers
ChineseLLMRegistry.get_all_providers() -> dict[str, ProviderInfo]
ChineseLLMRegistry.get_provider("zhipu") -> ProviderInfo | None
```

---

## LLM Config

Load priority (high → low):
```
$LLM_CONFIG_PATH  →  main/llm_config.json  →  {cwd}/llm_config.json  →  main/default_llm_config.json
```

```python
s = get_engine_settings()
# s.default_model  s.anthropic_api_key  s.openai_api_key  s.google_api_key
```

Env vars: `ANTHROPIC_API_KEY  OPENAI_API_KEY  GOOGLE_API_KEY  GLM_API_KEY  LLM_CONFIG_PATH`

---

## PermissionChecker

```python
class PermissionChecker:
    def __init__(self,
        allowed_tools: set[str],
        denied_tools: set[str],
        ask_tools: set[str],
    ): ...

    def check(self, tool_name: str, tool_input: dict) -> str:
        # must return "allow" | "deny" | "ask"
        ...
```

---

## Service — WorkspaceManager

```python
from Service.services.proxy.workspace_manager import WorkspaceManager
from Service.schemas.proxy import WorkspaceCreate

manager = WorkspaceManager()
ws_ctx = manager.create_workspace(WorkspaceCreate(
    workspace_id="ws-01",
    root_path="/projects/myapp",
    namespace="default",
    allowed_tools=["*"],            # or explicit list
    denied_tools=[],
    is_readonly=False,
    denied_paths=[".env", ".git"],
    max_file_size=10_485_760,
    enable_symlinks=False,
))
manager.get_workspace("ws-01") -> WorkspaceContext
manager.list_workspaces() -> list[str]
manager.remove_workspace("ws-01")
```

```python
# WorkspaceContext
ws_ctx.config.workspace_id -> str
ws_ctx.config.namespace -> str
ws_ctx.config.is_readonly -> bool
ws_ctx.resolved_root -> Path
ws_ctx.validate_path(path) -> tuple[bool, Path | None, str]
ws_ctx.validate_write_path(path) -> tuple[bool, Path | None, str]
ws_ctx.is_tool_allowed(tool_name) -> bool
```

---

## Service — Permission Bridge

```python
from Service.services.proxy.permission_bridge import (
    WorkspacePathValidator, WorkspacePermissionChecker,
    create_pyagentforge_permission_checker,
)

permission_checker = create_pyagentforge_permission_checker(
    WorkspacePermissionChecker(
        workspace_config=ws_ctx.config,
        path_validator=WorkspacePathValidator(ws_ctx),
    )
)
config = AgentConfig(permission_checker=permission_checker)
```

---

## Service — SessionManager

```python
from Service.services.proxy.session_manager import SessionManager

manager = SessionManager()
session  = manager.create_session(workspace_id="ws-01", agent_id="plan", metadata={})
session  = manager.get_session(session_id)
sessions = manager.list_sessions(workspace_id=None, agent_id=None) -> list[SessionResponse]
manager.delete_session(session_id)
manager.get_stats() -> dict   # {"total_sessions": N, "by_status": {...}}
```

```python
class SessionResponse:
    session_id: str         # "sess-xxxxxxxxxxxx"
    workspace_id: str
    agent_id: str
    status: str             # "active" | "idle" | "error"
    message_count: int
    created_at: str         # ISO-8601
    updated_at: str
    metadata: dict
```

---

## Service — AgentExecutor

```python
from Service.services.proxy.agent_executor import AgentExecutor, ExecutionResult

executor = AgentExecutor(workspace_context=ws_ctx)
await executor.initialize(
    agent_definition={
        "model":    {"id": "claude-3-5-sonnet-20241022", "temperature": 1.0, "max_tokens": 4096},
        "limits":   {"max_iterations": 50},
        "identity": {"description": "<system prompt>"},
        "capabilities": {"tools": ["*"], "denied_tools": []},
    },
    system_prompt=None,         # overrides identity.description if set
    config_overrides={          # all keys optional
        "model": "claude-3-5-haiku-20241022",
        "temperature": 0.5,
        "max_tokens": 2048,
        "max_iterations": 20,
        "timeout": 120,
        "system_prompt": "<override>",
    },
)

result: ExecutionResult = await executor.execute(prompt, context={})
async for event in executor.execute_stream(prompt, context={}): ...

executor.reset()
executor.get_context_summary() -> dict
```

```python
class ExecutionResult:
    success: bool
    output: str
    error: str | None
    iterations: int
    tool_calls: list[dict]
    metadata: dict          # {"session_id": ..., "model": ...}
```

---

## Service — AgentProxyService

```python
from Service.services.proxy.agent_proxy_service import AgentProxyService

ws_ctx  = proxy.create_workspace(WorkspaceCreate(...))
session = await proxy.create_session(SessionCreate(workspace_id="ws-01", agent_id="plan"))
result  = await proxy.execute(session_id=session.session_id, prompt="...", config_overrides={})
async for event in proxy.execute_stream(session_id=session.session_id, prompt="..."): ...
proxy.get_stats() -> dict   # {"workspaces": {...}, "sessions": {...}, "executor_cache_size": N}
```

---

## Service — AgentService

```python
from Service.services.agent_service import AgentService   # auto-init via create_app()

service.list_agents(namespace=None, tags=None) -> AgentListResponse
service.get_agent(agent_id) -> AgentInfoResponse
service.refresh_directory()
service.execute_agent(agent_id, task, context={}) -> AgentExecuteResponse
service.list_plans(namespace=None, status=None) -> PlanListResponse
service.get_plan(plan_id) -> PlanResponse
service.create_plan(PlanCreate(...)) -> PlanResponse
service.delete_plan(plan_id)
service.update_step(plan_id, step_id, StepUpdateRequest(...)) -> PlanResponse
service.add_step(plan_id, StepAddRequest(...)) -> PlanResponse
service.get_plan_stats() -> PlanStatsResponse
```

---

## Service — ModelConfigService

```python
from Service.services.model_config_service import ModelConfigService

service.list_models(provider=None, supports_vision=None, supports_tools=None) -> list[ModelConfigResponse]
service.get_model(model_id) -> ModelConfigResponse | None
service.create_model(ModelConfigCreate(...)) -> ModelConfigResponse
service.update_model(model_id, ModelConfigUpdate(...)) -> ModelConfigResponse
service.delete_model(model_id) -> bool     # raises ValueError for builtin model IDs
service.get_stats() -> ModelConfigStatsResponse
service.list_chinese_providers() -> ChineseProviderListResponse
service.get_chinese_provider(vendor) -> ChineseProviderInfo | None
```

Builtin model IDs (delete-protected):
```
claude-sonnet-4-20250514  claude-3-5-sonnet-20241022  claude-3-5-haiku-20241022
claude-opus-4-20250514    gpt-4o  gpt-4o-mini  o1-preview  o3-mini
gemini-2.0-flash          glm-4-flash  glm-4-plus  glm-4-air  glm-4-airx
glm-4-long  glm-4.7  glm-5
```

---

## Service — LegacyRuntimeService

```python
from Service.services.legacy_runtime_service import LegacyRuntimeService

await service.create_session(agent_id=None, system_prompt="...") -> {"session_id": str}
await service.send_message(session_id, message) -> {"role": "assistant", "content": str}
async for event in service.stream_message(session_id, message): ...
await service.delete_session(session_id)
service.list_sessions() -> list[dict]
service.create_agent(payload: dict) -> dict
service.get_agent(agent_id) -> dict
service.update_agent(agent_id, payload) -> dict
service.delete_agent(agent_id)
service.list_agents() -> list[dict]
```

---

## Schemas

```python
from Service.schemas import (
    ToolInfo,               # name: str, description: str, parameters: dict
    ExecuteToolRequest,     # tool_name: str, parameters: dict
    ExecuteToolResponse,    # tool_name: str, result: Any, error: str | None
)
from Service.schemas.proxy import (
    WorkspaceCreate,        # workspace_id*, root_path*, namespace, allowed_tools, denied_tools,
                            # is_readonly, denied_paths, max_file_size, enable_symlinks
    WorkspaceResponse,      # workspace_id, root_path, namespace, is_readonly, allowed_tools, denied_tools
    SessionCreate,          # workspace_id*, agent_id*, metadata
    SessionResponse,        # session_id, workspace_id, agent_id, status, message_count, created_at, updated_at, metadata
    ProxyExecuteRequest,    # session_id*, prompt*, context, config_overrides
    ProxyExecuteResponse,   # session_id, success, output, error, iterations, metadata
)
from Service.schemas.models import (
    ModelConfigCreate,      # id*, name*, provider*, api_type*, context_window, supports_*,  ...
    ModelConfigUpdate,      # all fields optional
    ModelConfigResponse,    # all ModelConfig fields + is_builtin, created_at, updated_at
)
from Service.schemas.agents import (
    PlanCreate,             # title*, objective*, priority, namespace, steps, estimated_complexity, metadata
    StepCreate,             # title*, description, dependencies, estimated_time, acceptance_criteria, files_affected
    StepUpdateRequest,      # status, notes
    StepAddRequest,         # title*, description, dependencies, estimated_time, acceptance_criteria, files_affected
    PlanResponse,           # id, title, objective, status, priority, namespace, steps, progress, change_log, ...
    AgentExecuteRequest,    # task*, context, namespace, options
    AgentExecuteResponse,   # agent_id, status, result, plan_id, error, started_at, completed_at
)
```

---

## App & Config

```python
from Service.gateway.app import create_app
from Service.core.registry import ServiceRegistry
from Service.config import get_settings

app = create_app()          # all services registered in lifespan
s = get_settings()
# s.legacy_sessions_dir  s.default_model  s.api_key
```

Env vars: `SERVICE_API_KEY  SERVICE_RATE_LIMIT_REQUESTS  SERVICE_LEGACY_SESSIONS_DIR  SERVICE_DEFAULT_MODEL`

```shell
uvicorn Service.gateway.app:create_app --factory --reload --port 8000
pytest tests/ -v --tb=short
```
