# SessionManager

## Import

```python
from Service.services.proxy.session_manager import SessionManager
from Service.schemas.proxy import SessionCreate, SessionResponse
```

## SessionResponse

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

## SessionManager

```python
manager = SessionManager()

session  = manager.create_session(workspace_id="ws-01", agent_id="plan", metadata={})
session  = manager.get_session(session_id) -> SessionResponse
sessions = manager.list_sessions(workspace_id=None, agent_id=None) -> list[SessionResponse]
manager.delete_session(session_id)
manager.get_stats() -> dict    # {"total_sessions": N, "by_status": {"active": N}}
```

Internal: each active session holds a cached `AgentExecutor` to avoid re-initialization.

## Session Lifecycle

```
create_session(workspace_id, agent_id)
  → WorkspaceContext resolved
  → AgentExecutor created (lazy, on first execute)
  → status = "active"
  → execute / execute_stream (multi-turn)
  → delete_session
```

## LegacyRuntimeService Sessions

Separate in-memory session store, not using Proxy sub-system:

```python
from Service.services.legacy_runtime_service import LegacyRuntimeService

result     = await service.create_session(agent_id=None, system_prompt="...")
# result   = {"session_id": "session_xxxxxxxxxxxx"}

response   = await service.send_message(result["session_id"], "hello")
# response = {"role": "assistant", "content": "..."}

async for event in service.stream_message(result["session_id"], "task"):
    # event["type"]: "stream" | "complete" | "error"
    pass

await service.delete_session(result["session_id"])
service.list_sessions() -> list[dict]
```
