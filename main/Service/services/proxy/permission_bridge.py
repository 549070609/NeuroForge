"""
Permission Bridge - 权限桥接器

将工作区域的路径验证和工具权限与 pyagentforge 的 PermissionChecker 集成。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyagentforge import PermissionChecker

logger = logging.getLogger(__name__)


class WorkspacePathValidator:
    """
    工作区域路径验证器

    封装 WorkspaceContext 的路径验证逻辑，供 PermissionChecker 使用。
    """

    def __init__(self, workspace_context: Any) -> None:
        """
        初始化路径验证器

        Args:
            workspace_context: WorkspaceContext 实例
        """
        self._context = workspace_context

    def validate_read_path(self, path: str | Path) -> tuple[bool, Path | None, str]:
        """
        验证读取路径

        Args:
            path: 要读取的路径

        Returns:
            (is_valid, resolved_path, error_message)
        """
        return self._context.validate_path(path)

    def validate_write_path(self, path: str | Path) -> tuple[bool, Path | None, str]:
        """
        验证写入路径

        Args:
            path: 要写入的路径

        Returns:
            (is_valid, resolved_path, error_message)
        """
        return self._context.validate_write_path(path)

    def validate_execute_path(self, path: str | Path) -> tuple[bool, Path | None, str]:
        """
        验证可执行路径

        Args:
            path: 可执行文件路径

        Returns:
            (is_valid, resolved_path, error_message)
        """
        return self._context.validate_path(path)

    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        检查工具是否被允许

        Args:
            tool_name: 工具名称

        Returns:
            是否允许
        """
        return self._context.is_tool_allowed(tool_name)


class WorkspacePermissionChecker:
    """
    工作区域权限检查器

    集成工作区域路径验证的权限检查器，兼容 pyagentforge 的 PermissionChecker 接口。
    """

    def __init__(
        self,
        workspace_config: Any,
        path_validator: WorkspacePathValidator | None = None,
        allowed_tools: set[str] | None = None,
        denied_tools: set[str] | None = None,
        ask_tools: set[str] | None = None,
    ) -> None:
        """
        初始化权限检查器

        Args:
            workspace_config: WorkspaceConfig 实例
            path_validator: 路径验证器 (可选)
            allowed_tools: 允许的工具集合
            denied_tools: 拒绝的工具集合
            ask_tools: 需要用户确认的工具集合
        """
        self._workspace_config = workspace_config
        self._path_validator = path_validator
        self._allowed_tools = allowed_tools or set()
        self._denied_tools = denied_tools or set()
        self._ask_tools = ask_tools or set()

        # 从工作区域配置继承工具权限
        if workspace_config:
            if "*" not in workspace_config.allowed_tools:
                self._allowed_tools = set(workspace_config.allowed_tools)
            self._denied_tools = set(workspace_config.denied_tools)

    def check(self, tool_name: str, tool_input: dict) -> str:
        """
        检查工具权限

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数

        Returns:
            权限结果: "allow", "deny", 或 "ask"
        """
        # 检查拒绝列表
        if tool_name in self._denied_tools:
            logger.debug(f"Tool denied by deny list: {tool_name}")
            return "deny"

        # 检查需要确认的工具
        if tool_name in self._ask_tools:
            logger.debug(f"Tool requires confirmation: {tool_name}")
            return "ask"

        # 检查允许列表
        if self._allowed_tools and tool_name not in self._allowed_tools:
            logger.debug(f"Tool denied by allow list: {tool_name}")
            return "deny"

        # 如果有路径验证器，检查路径相关参数
        if self._path_validator:
            path_result = self._check_path_in_input(tool_name, tool_input)
            if path_result != "allow":
                return path_result

        return "allow"

    def _check_path_in_input(self, tool_name: str, tool_input: dict) -> str:
        """
        检查工具输入中的路径参数

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数

        Returns:
            权限结果
        """
        # 常见的路径参数名
        path_keys = ["path", "file_path", "file", "directory", "dir", "destination", "target"]

        # 写入工具
        write_tools = {"write", "edit", "create", "mkdir", "rm", "delete", "move"}

        for key in path_keys:
            if key in tool_input:
                path = tool_input[key]

                # 检查是读取还是写入操作
                if tool_name.lower() in write_tools or "write" in key.lower():
                    is_valid, _, error = self._path_validator.validate_write_path(path)
                else:
                    is_valid, _, error = self._path_validator.validate_read_path(path)

                if not is_valid:
                    logger.warning(f"Path validation failed for tool {tool_name}: {error}")
                    return "deny"

        return "allow"

    def check_path(self, path: str | Path, is_write: bool = False) -> tuple[bool, str]:
        """
        直接检查路径权限

        Args:
            path: 要检查的路径
            is_write: 是否为写入操作

        Returns:
            (is_allowed, error_message)
        """
        if not self._path_validator:
            return True, ""

        if is_write:
            is_valid, _, error = self._path_validator.validate_write_path(path)
        else:
            is_valid, _, error = self._path_validator.validate_read_path(path)

        return is_valid, error


def create_permission_checker_from_workspace(
    workspace_config: Any,
    path_validator: WorkspacePathValidator | None = None,
    ask_tools: set[str] | None = None,
) -> WorkspacePermissionChecker:
    """
    从工作区域配置创建权限检查器

    这是一个工厂函数，用于创建配置好的权限检查器。

    Args:
        workspace_config: WorkspaceConfig 实例
        path_validator: 路径验证器 (可选)
        ask_tools: 需要用户确认的工具集合

    Returns:
        WorkspacePermissionChecker 实例
    """
    return WorkspacePermissionChecker(
        workspace_config=workspace_config,
        path_validator=path_validator,
        ask_tools=ask_tools,
    )


def create_pyagentforge_permission_checker(
    workspace_permission_checker: WorkspacePermissionChecker,
) -> PermissionChecker:
    """
    创建 pyagentforge 兼容的 PermissionChecker

    这个函数创建一个适配器，使 WorkspacePermissionChecker 可以用于 pyagentforge。

    Args:
        workspace_permission_checker: WorkspacePermissionChecker 实例

    Returns:
        PermissionChecker 实例 (pyagentforge 兼容)
    """

    class AdaptedPermissionChecker(PermissionChecker):
        def __init__(self, workspace_checker: WorkspacePermissionChecker) -> None:
            super().__init__(
                allowed_tools=workspace_checker._allowed_tools,
                denied_tools=workspace_checker._denied_tools,
                ask_tools=workspace_checker._ask_tools,
            )
            self._workspace_checker = workspace_checker

        def check(self, tool_name: str, tool_input: dict) -> str:
            return self._workspace_checker.check(tool_name, tool_input)

    return AdaptedPermissionChecker(workspace_permission_checker)
