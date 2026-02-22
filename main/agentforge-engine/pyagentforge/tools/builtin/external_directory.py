"""
External Directory 工具

处理外部目录操作
"""

import shutil
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ExternalDirectoryTool(BaseTool):
    """ExternalDirectory 工具 - 外部目录操作"""

    name = "external_directory"
    description = """操作外部目录。

支持:
- 挂载: 添加外部目录到工作区
- 卸载: 移除已挂载的目录
- 列出: 显示所有挂载的目录
- 同步: 同步外部目录内容

用于处理项目外部的文件和目录。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["mount", "unmount", "list", "sync", "copy"],
                "description": "操作类型",
            },
            "source": {
                "type": "string",
                "description": "源目录路径",
            },
            "target": {
                "type": "string",
                "description": "目标路径",
            },
            "name": {
                "type": "string",
                "description": "挂载点名称",
            },
        },
        "required": ["action"],
    }
    timeout = 120
    risk_level = "high"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
        workspace_root: str | None = None,
    ) -> None:
        self.permission_checker = permission_checker
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._mounts: dict[str, dict[str, Any]] = {}

    async def execute(
        self,
        action: str,
        source: str | None = None,
        target: str | None = None,
        name: str | None = None,
    ) -> str:
        """执行外部目录操作"""
        logger.info(
            "External directory action",
            extra_data={"action": action, "source": source},
        )

        if action == "mount":
            return await self._mount(source, name)
        elif action == "unmount":
            return await self._unmount(name)
        elif action == "list":
            return self._list_mounts()
        elif action == "sync":
            return await self._sync(name)
        elif action == "copy":
            return await self._copy(source, target)
        else:
            return f"Error: Unknown action '{action}'"

    async def _mount(self, source: str | None, name: str | None) -> str:
        """挂载外部目录"""
        if not source:
            return "Error: source is required for mount action"

        source_path = Path(source).resolve()

        # 检查权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(source_path)) == PermissionResult.DENY:
                return f"Error: Access to '{source}' is denied"

        if not source_path.exists():
            return f"Error: Source '{source}' does not exist"

        if not source_path.is_dir():
            return f"Error: '{source}' is not a directory"

        mount_name = name or source_path.name

        if mount_name in self._mounts:
            return f"Error: Mount point '{mount_name}' already exists"

        self._mounts[mount_name] = {
            "source": str(source_path),
            "mounted_at": str(self.workspace_root / "external" / mount_name),
        }

        return f"Mounted '{source_path}' as '{mount_name}'"

    async def _unmount(self, name: str | None) -> str:
        """卸载挂载点"""
        if not name:
            return "Error: name is required for unmount action"

        if name not in self._mounts:
            return f"Error: Mount point '{name}' not found"

        del self._mounts[name]
        return f"Unmounted '{name}'"

    def _list_mounts(self) -> str:
        """列出所有挂载点"""
        if not self._mounts:
            return "No external directories mounted."

        lines = ["Mounted external directories:", "-" * 40]
        for name, info in self._mounts.items():
            lines.append(f"  {name}:")
            lines.append(f"    Source: {info['source']}")

        return "\n".join(lines)

    async def _sync(self, name: str | None) -> str:
        """同步挂载点"""
        if not name:
            return "Error: name is required for sync action"

        if name not in self._mounts:
            return f"Error: Mount point '{name}' not found"

        mount_info = self._mounts[name]
        source = Path(mount_info["source"])
        target = Path(mount_info["mounted_at"])

        try:
            if target.exists():
                shutil.rmtree(target)

            shutil.copytree(source, target)

            return f"Synced '{name}' from {source} to {target}"

        except Exception as e:
            return f"Error syncing: {str(e)}"

    async def _copy(self, source: str | None, target: str | None) -> str:
        """复制文件或目录"""
        if not source or not target:
            return "Error: source and target are required for copy action"

        source_path = Path(source)
        target_path = Path(target)

        # 检查权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(source_path)) == PermissionResult.DENY:
                return f"Error: Access to '{source}' is denied"

        if not source_path.exists():
            return f"Error: Source '{source}' does not exist"

        try:
            if source_path.is_dir():
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(source_path, target_path)
                return f"Copied directory '{source}' to '{target}'"
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
                return f"Copied file '{source}' to '{target}'"

        except Exception as e:
            return f"Error copying: {str(e)}"


class WorkspaceTool(BaseTool):
    """Workspace 工具 - 工作区管理"""

    name = "workspace"
    description = """管理工作区。

操作:
- info: 显示工作区信息
- add_path: 添加路径到工作区
- remove_path: 从工作区移除路径
- clean: 清理工作区临时文件
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["info", "add_path", "remove_path", "clean"],
                "description": "操作类型",
            },
            "path": {
                "type": "string",
                "description": "路径 (add_path/remove_path 使用)",
            },
        },
        "required": ["action"],
    }
    timeout = 30
    risk_level = "medium"

    def __init__(self, workspace_root: str | None = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._paths: set[str] = {str(self.workspace_root)}

    async def execute(
        self,
        action: str,
        path: str | None = None,
    ) -> str:
        """执行工作区操作"""
        if action == "info":
            return self._get_info()
        elif action == "add_path":
            return self._add_path(path)
        elif action == "remove_path":
            return self._remove_path(path)
        elif action == "clean":
            return await self._clean()
        else:
            return f"Error: Unknown action '{action}'"

    def _get_info(self) -> str:
        """获取工作区信息"""
        lines = [
            "Workspace Information",
            "=" * 40,
            f"Root: {self.workspace_root}",
            f"Paths: {len(self._paths)}",
            "",
            "Tracked paths:",
        ]

        for p in sorted(self._paths):
            path = Path(p)
            if path.exists():
                status = "directory" if path.is_dir() else "file"
                lines.append(f"  • {p} ({status})")
            else:
                lines.append(f"  • {p} (not found)")

        return "\n".join(lines)

    def _add_path(self, path: str | None) -> str:
        """添加路径"""
        if not path:
            return "Error: path is required for add_path action"

        resolved = str(Path(path).resolve())
        self._paths.add(resolved)
        return f"Added '{resolved}' to workspace"

    def _remove_path(self, path: str | None) -> str:
        """移除路径"""
        if not path:
            return "Error: path is required for remove_path action"

        resolved = str(Path(path).resolve())
        if resolved in self._paths:
            self._paths.remove(resolved)
            return f"Removed '{resolved}' from workspace"
        return f"Path '{resolved}' not in workspace"

    async def _clean(self) -> str:
        """清理临时文件"""
        cleaned = []

        patterns = ["**/__pycache__", "**/*.pyc", "**/.DS_Store", "**/*.tmp"]

        for path_str in self._paths:
            path = Path(path_str)
            if not path.exists():
                continue

            for pattern in patterns:
                for item in path.rglob(pattern.replace("**/", "")):
                    try:
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
                        cleaned.append(str(item))
                    except Exception:
                        pass

        if cleaned:
            return f"Cleaned {len(cleaned)} items:\n" + "\n".join(f"  • {c}" for c in cleaned[:20])
        return "No temporary files to clean"
