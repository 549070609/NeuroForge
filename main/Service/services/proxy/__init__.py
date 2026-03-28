"""Proxy services package with lazy exports to avoid eager heavy imports."""

from __future__ import annotations

from importlib import import_module

_EXPORT_MAP = {
    "WorkspaceConfig": "workspace_manager",
    "WorkspaceContext": "workspace_manager",
    "WorkspaceManager": "workspace_manager",
    "WorkspacePermissionChecker": "permission_bridge",
    "WorkspacePathValidator": "permission_bridge",
    "create_permission_checker_from_workspace": "permission_bridge",
    "AgentExecutor": "agent_executor",
    "SessionManager": "session_manager",
    "SessionState": "session_manager",
    "AgentProxyService": "agent_proxy_service",
}

__all__ = list(_EXPORT_MAP.keys())


def __getattr__(name: str):
    module_name = _EXPORT_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, name)
