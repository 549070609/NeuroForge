"""
工具执行沙箱

为高风险工具提供 subprocess 级别的隔离执行。
不修改现有 ToolExecutor，而是作为可选的执行后端。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SANDBOXED_TOOLS = {"Bash", "Write", "Edit"}


@dataclass
class SandboxConfig:
    """沙箱配置"""

    enabled: bool = True
    timeout_seconds: float = 30.0
    sandboxed_tool_names: set[str] = field(
        default_factory=lambda: set(DEFAULT_SANDBOXED_TOOLS)
    )
    max_output_bytes: int = 1_000_000
    working_directory: str | None = None


@dataclass
class SandboxResult:
    """沙箱执行结果"""

    success: bool
    output: str
    error: str = ""
    exit_code: int = 0
    elapsed_ms: int = 0


class SandboxExecutor:
    """通过 subprocess 隔离执行工具

    将工具的 execute() 调用序列化为 JSON，
    在子进程中执行，收集输出并返回。
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig()

    def should_sandbox(self, tool_name: str) -> bool:
        """判断工具是否需要沙箱执行"""
        return (
            self.config.enabled
            and tool_name in self.config.sandboxed_tool_names
        )

    async def execute_in_sandbox(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> SandboxResult:
        """在隔离子进程中执行工具

        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数

        Returns:
            SandboxResult
        """
        import time

        start = time.monotonic()

        runner_script = self._generate_runner_script(tool_name, tool_input)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(runner_script)
            script_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_directory,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.config.timeout_seconds,
                )
            except TimeoutError:
                proc.kill()
                await proc.communicate()
                elapsed = int((time.monotonic() - start) * 1000)
                return SandboxResult(
                    success=False,
                    output="",
                    error=f"Sandbox timeout after {self.config.timeout_seconds}s",
                    exit_code=-1,
                    elapsed_ms=elapsed,
                )

            elapsed = int((time.monotonic() - start) * 1000)
            stdout_text = stdout.decode("utf-8", errors="replace")[: self.config.max_output_bytes]
            stderr_text = stderr.decode("utf-8", errors="replace")[: self.config.max_output_bytes]

            return SandboxResult(
                success=proc.returncode == 0,
                output=stdout_text,
                error=stderr_text,
                exit_code=proc.returncode or 0,
                elapsed_ms=elapsed,
            )

        finally:
            with contextlib.suppress(Exception):
                Path(script_path).unlink(missing_ok=True)

    @staticmethod
    def _generate_runner_script(tool_name: str, tool_input: dict[str, Any]) -> str:
        """生成在子进程中执行工具的 Python 脚本"""
        input_json = json.dumps(tool_input, ensure_ascii=False)
        return f"""
import asyncio
import json
import sys

async def main():
    tool_name = {tool_name!r}
    tool_input = json.loads({input_json!r})

    if tool_name == "Bash":
        import subprocess
        cmd = tool_input.get("command", "echo no command")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=25
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)
        except subprocess.TimeoutExpired:
            print("Command timed out", file=sys.stderr)
            sys.exit(1)

    elif tool_name == "Write":
        path = tool_input.get("path", "")
        contents = tool_input.get("contents", "")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(contents)
            print(f"Written {{len(contents)}} chars to {{path}}")
        except Exception as e:
            print(f"Error: {{e}}", file=sys.stderr)
            sys.exit(1)

    elif tool_name == "Edit":
        path = tool_input.get("path", "")
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if old not in content:
                print("old_string not found", file=sys.stderr)
                sys.exit(1)
            content = content.replace(old, new, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Edited {{path}}")
        except Exception as e:
            print(f"Error: {{e}}", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown tool: {{tool_name}}", file=sys.stderr)
        sys.exit(1)

asyncio.run(main())
"""
