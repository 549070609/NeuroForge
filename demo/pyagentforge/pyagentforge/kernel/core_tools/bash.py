"""
Bash 工具

执行 shell 命令
"""

import asyncio
import logging
from typing import Any

from pyagentforge.kernel.base_tool import BaseTool

logger = logging.getLogger(__name__)


class BashTool(BaseTool):
    """Bash 工具 - 执行 shell 命令"""

    name = "bash"
    description = """在持久的 shell 会话中执行命令。

关键行为:
- 命令在非交互式 shell 中执行
- 工作目录在命令之间保持不变
- 超时后终止命令

适用于: git、npm、docker、pytest 和其他 CLI 工具。
避免: 读取/写入文件(使用专用工具代替)。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间(毫秒)，默认 120000",
                "default": 120000,
            },
            "description": {
                "type": "string",
                "description": "命令用途的简短描述",
            },
        },
        "required": ["command"],
    }
    timeout = 120
    risk_level = "high"

    def __init__(self, working_dir: str | None = None) -> None:
        self.working_dir = working_dir

    async def execute(
        self,
        command: str,
        timeout: int = 120000,
        description: str = "",
    ) -> str:
        """执行 shell 命令"""
        logger.info(f"Executing bash command: {command}")

        timeout_sec = timeout / 1000

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return f"Error: Command timed out after {timeout_sec} seconds"

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            result_parts = []
            if stdout_str:
                result_parts.append(stdout_str)
            if stderr_str:
                result_parts.append(f"[stderr]\n{stderr_str}")

            result = "\n".join(result_parts) if result_parts else "(no output)"

            if process.returncode != 0:
                result = f"Exit code: {process.returncode}\n{result}"

            logger.debug(f"Bash command completed: returncode={process.returncode}")

            return result

        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            logger.error(f"Bash command error: {str(e)}")
            return error_msg
