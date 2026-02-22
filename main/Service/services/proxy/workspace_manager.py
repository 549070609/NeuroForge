"""
Workspace Manager - 工作区域管理器

提供工作区域的创建、验证和隔离功能。
实现路径安全检查，防止路径遍历和符号链接攻击。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# 敏感文件/目录模式
SENSITIVE_PATTERNS = {
    ".env",
    ".git",
    ".ssh",
    ".gnupg",
    ".config",
    "credentials",
    "secrets",
    "private",
    "id_rsa",
    "id_ed25519",
    "*.pem",
    "*.key",
}


class WorkspaceConfig(BaseModel):
    """工作区域配置"""

    root_path: str = Field(description="工作区域根路径")
    namespace: str = Field(default="default", description="命名空间")
    allowed_tools: list[str] = Field(default=["*"], description="允许的工具列表")
    denied_tools: list[str] = Field(default=[], description="拒绝的工具列表")
    is_readonly: bool = Field(default=False, description="是否只读模式")
    denied_paths: list[str] = Field(default=[], description="拒绝访问的路径模式")
    max_file_size: int = Field(default=10 * 1024 * 1024, description="最大文件大小 (字节)")
    enable_symlinks: bool = Field(default=False, description="是否允许符号链接")

    @field_validator("root_path")
    @classmethod
    def validate_root_path(cls, v: str) -> str:
        """验证根路径"""
        path = Path(v)
        if not path.is_absolute():
            # 转换为绝对路径
            path = path.resolve()
        return str(path)


@dataclass
class WorkspaceContext:
    """
    工作区域上下文

    存储工作区域的运行时状态和验证方法。
    """

    workspace_id: str
    config: WorkspaceConfig
    resolved_root: Path = field(init=False)
    _denied_patterns: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        """初始化后处理"""
        self.resolved_root = Path(self.config.root_path).resolve()
        self._denied_patterns = set(SENSITIVE_PATTERNS) | set(self.config.denied_paths)

    def validate_path(self, path: str | Path) -> tuple[bool, Path | None, str]:
        """
        验证路径是否在工作区域内且安全

        Args:
            path: 要验证的路径

        Returns:
            (is_valid, resolved_path, error_message)
        """
        try:
            target = Path(path)

            # 处理相对路径
            if not target.is_absolute():
                target = self.resolved_root / target

            # 解析路径（处理 .. 和 .）
            try:
                resolved = target.resolve(strict=False)
            except Exception as e:
                return False, None, f"Path resolution failed: {e}"

            # 检查是否在工作区域根目录内
            try:
                resolved.relative_to(self.resolved_root)
            except ValueError:
                return False, None, "Path outside workspace root"

            # 检查符号链接
            if not self.config.enable_symlinks and self._is_symlink(resolved):
                return False, None, "Symlinks are not allowed in this workspace"

            # 检查敏感文件
            if self._is_sensitive_path(resolved):
                return False, None, "Access to sensitive files is not allowed"

            # 检查路径是否存在于拒绝列表中
            for pattern in self.config.denied_paths:
                if self._match_pattern(resolved, pattern):
                    return False, None, f"Path matches denied pattern: {pattern}"

            return True, resolved, ""

        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return False, None, f"Validation error: {e}"

    def validate_write_path(self, path: str | Path) -> tuple[bool, Path | None, str]:
        """
        验证写入路径

        对于只读工作区域，禁止所有写入操作。

        Args:
            path: 要写入的路径

        Returns:
            (is_valid, resolved_path, error_message)
        """
        if self.config.is_readonly:
            return False, None, "Workspace is read-only"

        return self.validate_path(path)

    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        检查工具是否被允许

        Args:
            tool_name: 工具名称

        Returns:
            是否允许
        """
        # 先检查拒绝列表
        if tool_name in self.config.denied_tools:
            return False

        # 检查允许列表
        if "*" in self.config.allowed_tools:
            return True

        return tool_name in self.config.allowed_tools

    def _is_symlink(self, path: Path) -> bool:
        """检查路径是否为符号链接"""
        try:
            # 检查路径本身
            if path.is_symlink():
                return True

            # 检查父目录中的符号链接
            for parent in path.parents:
                if parent == self.resolved_root:
                    break
                if parent.is_symlink():
                    return True

            return False
        except Exception:
            return False

    def _is_sensitive_path(self, path: Path) -> bool:
        """检查是否为敏感路径"""
        path_str = str(path).lower()
        path_parts = [p.lower() for p in path.parts]

        for pattern in self._denied_patterns:
            # 精确匹配
            if pattern.lower() in path_parts:
                return True

            # 后缀匹配 (如 *.pem)
            if pattern.startswith("*."):
                ext = pattern[1:]  # .pem
                if path_str.endswith(ext):
                    return True

            # 子字符串匹配
            if pattern.lower() in path_str:
                return True

        return False

    def _match_pattern(self, path: Path, pattern: str) -> bool:
        """匹配路径模式"""
        path_str = str(path).lower()
        pattern_lower = pattern.lower()

        # 简单匹配
        if pattern_lower in path_str:
            return True

        # 通配符匹配
        if "*" in pattern:
            import fnmatch

            return fnmatch.fnmatch(path_str, pattern_lower)

        return False

    def get_safe_relative_path(self, path: str | Path) -> str | None:
        """
        获取安全的相对路径

        Args:
            path: 绝对或相对路径

        Returns:
            相对于工作区域根目录的路径，或 None 如果无效
        """
        is_valid, resolved, _ = self.validate_path(path)
        if not is_valid or resolved is None:
            return None

        try:
            return str(resolved.relative_to(self.resolved_root))
        except ValueError:
            return None


class WorkspaceManager:
    """
    工作区域管理器

    管理多个工作区域的创建、查询和删除。
    """

    def __init__(self) -> None:
        self._workspaces: dict[str, WorkspaceContext] = {}
        self._logger = logging.getLogger(f"{__name__}.WorkspaceManager")

    def create_workspace(
        self,
        workspace_id: str,
        config: WorkspaceConfig | dict[str, Any],
    ) -> WorkspaceContext:
        """
        创建工作区域

        Args:
            workspace_id: 工作区域 ID
            config: 工作区域配置

        Returns:
            WorkspaceContext 实例

        Raises:
            ValueError: 如果配置无效
        """
        if workspace_id in self._workspaces:
            self._logger.warning(f"Overwriting existing workspace: {workspace_id}")

        if isinstance(config, dict):
            config = WorkspaceConfig(**config)

        # 验证根路径
        root = Path(config.root_path)
        if not root.exists():
            try:
                root.mkdir(parents=True, exist_ok=True)
                self._logger.info(f"Created workspace directory: {root}")
            except Exception as e:
                raise ValueError(f"Failed to create workspace directory: {e}")

        # 创建上下文
        context = WorkspaceContext(workspace_id=workspace_id, config=config)
        self._workspaces[workspace_id] = context

        self._logger.info(f"Created workspace: {workspace_id} at {config.root_path}")
        return context

    def get_workspace(self, workspace_id: str) -> WorkspaceContext | None:
        """
        获取工作区域

        Args:
            workspace_id: 工作区域 ID

        Returns:
            WorkspaceContext 或 None
        """
        return self._workspaces.get(workspace_id)

    def remove_workspace(self, workspace_id: str) -> bool:
        """
        移除工作区域

        注意：这不会删除文件系统上的目录，只是从管理器中移除。

        Args:
            workspace_id: 工作区域 ID

        Returns:
            是否成功移除
        """
        if workspace_id in self._workspaces:
            del self._workspaces[workspace_id]
            self._logger.info(f"Removed workspace: {workspace_id}")
            return True
        return False

    def list_workspaces(self) -> list[str]:
        """列出所有工作区域 ID"""
        return list(self._workspaces.keys())

    def clear(self) -> None:
        """清空所有工作区域"""
        self._workspaces.clear()
        self._logger.info("Cleared all workspaces")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_workspaces": len(self._workspaces),
            "workspaces": [
                {
                    "id": ws_id,
                    "root": ctx.config.root_path,
                    "namespace": ctx.config.namespace,
                    "readonly": ctx.config.is_readonly,
                }
                for ws_id, ctx in self._workspaces.items()
            ],
        }
