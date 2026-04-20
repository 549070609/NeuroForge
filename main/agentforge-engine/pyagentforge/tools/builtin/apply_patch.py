"""
ApplyPatch 工具

应用 Git 补丁
"""

import asyncio
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ApplyPatchTool(BaseTool):
    """ApplyPatch 宸ュ叿 - 应用补丁"""

    name = "apply_patch"
    description = """应用 Git 格式的补丁。

支持:
- unified diff 格式
- 多文件补丁
- 模拟应用 (--check)

补丁格式示例:
```diff
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old line
+new line
 context
```
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "patch": {
                "type": "string",
                "description": "补丁内容 (unified diff 格式)",
            },
            "patch_file": {
                "type": "string",
                "description": "补丁文件路径",
            },
            "check": {
                "type": "boolean",
                "description": "只检查不应用",
                "default": False,
            },
            "reverse": {
                "type": "boolean",
                "description": "反向应用 (撤销)",
                "default": False,
            },
            "strip": {
                "type": "integer",
                "description": "路径前缀去除级别",
                "default": 1,
            },
        },
    }
    timeout = 60
    risk_level = "high"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
        working_dir: str | None = None,
    ) -> None:
        self.permission_checker = permission_checker
        self.working_dir = working_dir

    async def execute(
        self,
        patch: str | None = None,
        patch_file: str | None = None,
        check: bool = False,
        reverse: bool = False,
        strip: int = 1,
    ) -> str:
        """应用补丁"""
        if not patch and not patch_file:
            return "Error: Either patch or patch_file must be provided"

        logger.info(
            "Applying patch",
            extra_data={"check": check, "reverse": reverse},
        )

        # 读取补丁文件
        if patch_file:
            path = Path(patch_file)

            if self.permission_checker:
                from pyagentforge.tools.permission import PermissionResult

                if self.permission_checker.check_path(str(path)) == PermissionResult.DENY:
                    return f"Error: Access to '{patch_file}' is denied"

            if not path.exists():
                return f"Error: Patch file '{patch_file}' not found"

            with open(path) as f:
                patch = f.read()

        # 解析补丁影响的文件
        affected_files = self._parse_affected_files(patch)

        #
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            for f in affected_files:
                if self.permission_checker.check_path(f) == PermissionResult.DENY:
                    return f"Error: Cannot modify '{f}' - access denied"

        # 使用 git apply 鎴?patch 鍛戒护
        try:
            # 浼樺厛使用 git apply
            result = await self._git_apply(patch, check, reverse, strip)

            if "not a git repository" in result.lower():
                #
                result = await self._patch_command(patch, check, reverse, strip)

            return result

        except Exception as e:
            logger.error(
                "Apply patch error",
                extra_data={"error": str(e)},
            )
            return f"Error applying patch: {str(e)}"

    async def _git_apply(
        self,
        patch: str,
        check: bool,
        reverse: bool,
        strip: int,
    ) -> str:
        """使用 git apply"""
        cmd = ["git", "apply"]

        if check:
            cmd.append("--check")
        if reverse:
            cmd.append("--reverse")
        cmd.extend(["-p", str(strip)])

        #
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_dir,
        )

        stdout, stderr = await process.communicate(patch.encode())

        if process.returncode == 0:
            if check:
                return "Patch would apply successfully (dry run)"
            return "Patch applied successfully\nAffected files:\n" + "\n".join(
                f"  - {f}" for f in self._parse_affected_files(patch)
            )
        else:
            error = stderr.decode() if stderr else "Unknown error"
            return f"Error applying patch:\n{error}"

    async def _patch_command(
        self,
        patch: str,
        check: bool,
        reverse: bool,
        strip: int,
    ) -> str:
        """使用 patch 命令"""
        cmd = ["patch"]

        if check:
            cmd.extend(["--dry-run"])
        if reverse:
            cmd.extend(["--reverse"])
        cmd.extend(["-p", str(strip)])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_dir,
        )

        stdout, stderr = await process.communicate(patch.encode())

        output = stdout.decode() if stdout else ""
        error = stderr.decode() if stderr else ""

        if process.returncode == 0:
            return f"Patch applied successfully\n{output}"
        else:
            return f"Error applying patch:\n{error}\n{output}"

    def _parse_affected_files(self, patch: str) -> list[str]:
        """解析补丁影响的文件"""
        import re

        files = []
        # 匹配 --- a/file 和 +++ b/file
        for match in re.finditer(r'^[+-]{3}\s+[ab]/(.+)$', patch, re.MULTILINE):
            files.append(match.group(1))

        return list(set(files))


class DiffTool(BaseTool):
    """"""

    name = "diff"
    description = """生成文件或目录的差异。

比较:
- 两个文件
- 文件的不同版本
- 两个目录
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "file1": {
                "type": "string",
                "description": "第一个文件路径",
            },
            "file2": {
                "type": "string",
                "description": "第二个文件路径",
            },
            "context_lines": {
                "type": "integer",
                "description": "上下文行数",
                "default": 3,
            },
        },
        "required": ["file1", "file2"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(
        self,
        file1: str,
        file2: str,
        context_lines: int = 3,
    ) -> str:
        """"""
        path1 = Path(file1)
        path2 = Path(file2)

        if not path1.exists():
            return f"Error: '{file1}' does not exist"
        if not path2.exists():
            return f"Error: '{file2}' does not exist"

        try:
            import difflib

            with open(path1) as f:
                lines1 = f.readlines()
            with open(path2) as f:
                lines2 = f.readlines()

            diff = difflib.unified_diff(
                lines1,
                lines2,
                fromfile=file1,
                tofile=file2,
                lineterm="",
                n=context_lines,
            )

            result = "\n".join(diff)

            if not result:
                return "Files are identical"

            return result

        except Exception as e:
            return f"Error generating diff: {str(e)}"


