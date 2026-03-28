# WorkspaceManager

## Import

```python
from Service.services.proxy.workspace_manager import WorkspaceManager
from Service.schemas.proxy import WorkspaceCreate, WorkspaceResponse
from Service.services.proxy.permission_bridge import (
    WorkspacePathValidator,
    WorkspacePermissionChecker,
    create_permission_checker_from_workspace,
)
```

## WorkspaceCreate

```python
class WorkspaceCreate:
    workspace_id: str                      # required
    root_path: str                         # required, absolute path
    namespace: str = "default"
    allowed_tools: list[str] = ["*"]      # "*" = all tools
    denied_tools: list[str] = []
    is_readonly: bool = False
    denied_paths: list[str] = []          # glob patterns, e.g. [".env", ".git"]
    max_file_size: int = 10_485_760       # bytes (10 MB)
    enable_symlinks: bool = False
```

## WorkspaceManager

```python
manager = WorkspaceManager()

ws_ctx = manager.create_workspace(
    "ws-01",
    WorkspaceCreate(
        workspace_id="ws-01",
        root_path="/projects/myapp",
        allowed_tools=["read", "write", "bash"],
        denied_paths=[".env", ".git"],
    ).model_dump(exclude={"workspace_id"}),
)

manager.get_workspace("ws-01") -> WorkspaceContext
manager.list_workspaces() -> list[str]
manager.remove_workspace("ws-01")          # removes from memory, not from disk
```

## WorkspaceContext

```python
ws_ctx.workspace_id -> str
ws_ctx.config.namespace -> str
ws_ctx.config.is_readonly -> bool
ws_ctx.config.allowed_tools -> list[str]
ws_ctx.config.denied_tools -> list[str]
ws_ctx.resolved_root -> Path

ws_ctx.validate_path(path) -> tuple[bool, Path | None, str]
ws_ctx.validate_write_path(path) -> tuple[bool, Path | None, str]
ws_ctx.is_tool_allowed(tool_name) -> bool
```

## Permission Bridge

Adapts workspace rules to `pyagentforge.PermissionChecker`:

```python
checker = create_permission_checker_from_workspace(
    ws_ctx.config,
    path_validator=WorkspacePathValidator(ws_ctx),
)
# Inject into AgentConfig — engine checks before every tool call
config = AgentConfig(permission_checker=checker)
```

`WorkspacePermissionChecker.check(tool_name, tool_input) -> "allow" | "deny" | "ask"`
