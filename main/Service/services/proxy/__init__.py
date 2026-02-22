"""
Proxy Services - 代理 Agent 服务模块

提供工作区域隔离、会话管理和 Agent 执行功能。
"""

from .workspace_manager import (
    WorkspaceConfig,
    WorkspaceContext,
    WorkspaceManager,
)
from .permission_bridge import (
    WorkspacePermissionChecker,
    WorkspacePathValidator,
    create_permission_checker_from_workspace,
)
from .agent_executor import AgentExecutor
from .session_manager import SessionManager, SessionState
from .agent_proxy_service import AgentProxyService

__all__ = [
    # Workspace
    "WorkspaceConfig",
    "WorkspaceContext",
    "WorkspaceManager",
    # Permission
    "WorkspacePermissionChecker",
    "WorkspacePathValidator",
    "create_permission_checker_from_workspace",
    # Execution
    "AgentExecutor",
    # Session
    "SessionManager",
    "SessionState",
    # Service
    "AgentProxyService",
]
