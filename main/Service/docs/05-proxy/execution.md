# AgentExecutor & AgentProxyService

## AgentExecutor

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
    system_prompt=None,        # overrides identity.description when set
    config_overrides={         # all optional
        "model": "claude-3-5-haiku-20241022",
        "temperature": 0.5,
        "max_tokens": 2048,
        "max_iterations": 20,
        "timeout": 120,
        "system_prompt": "<override>",
    },
)

result: ExecutionResult = await executor.execute(prompt, context={})

async for event in executor.execute_stream(prompt, context={}):
    # event["type"]: "stream" | "tool_start" | "tool_result" | "complete" | "error"
    pass

executor.reset()
executor.get_context_summary() -> dict
```

## ExecutionResult

```python
class ExecutionResult:
    success: bool
    output: str
    error: str | None
    iterations: int
    tool_calls: list[dict]
    metadata: dict         # {"session_id": ..., "model": ...}
```

## Stream Events

```python
# type == "stream"
event["event"]["delta"] -> str          # incremental text chunk

# type == "tool_start"
event["tool_name"] -> str
event["tool_id"] -> str

# type == "tool_result"
event["result"] -> str

# type == "complete"
event["text"] -> str                    # full final output

# type == "error"
event["message"] -> str
```

## AgentProxyService

```python
from Service.services.proxy.agent_proxy_service import AgentProxyService
from Service.schemas.proxy import (
    WorkspaceCreate, SessionCreate,
    ProxyExecuteRequest, ProxyExecuteResponse,
)

ws_ctx  = proxy.create_workspace(WorkspaceCreate(...))
session = await proxy.create_session(SessionCreate(workspace_id="ws-01", agent_id="plan"))
result  = await proxy.execute(
    session_id=session.session_id,
    prompt="analyze payment module",
    context={"focus": "retry_logic"},
    config_overrides={"max_iterations": 20},
)
async for event in proxy.execute_stream(
    session_id=session.session_id,
    prompt="step-by-step optimization",
): ...
proxy.get_stats() -> dict
```

## ProxyExecuteRequest / ProxyExecuteResponse

```python
class ProxyExecuteRequest:
    session_id: str
    prompt: str
    context: dict | None = None
    config_overrides: dict | None = None   # same keys as AgentExecutor.initialize config_overrides

class ProxyExecuteResponse:
    session_id: str
    success: bool
    output: str
    error: str | None
    iterations: int
    metadata: dict
```
