"""
工具执行器

负责执行工具调用并返回结果
"""

import asyncio
import traceback
from typing import Any

from pyagentforge.config.settings import get_settings
from pyagentforge.core.message import ToolUseBlock
from pyagentforge.tools.permission import PermissionChecker, PermissionResult
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """工具执行器"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        timeout: int | None = None,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        """
        初始化工具执行器

        Args:
            tool_registry: 工具注册表
            timeout: 执行超时时间(秒)
            permission_checker: 权限检查器
        """
        settings = get_settings()
        self.registry = tool_registry
        self.timeout = timeout or settings.tool_timeout
        self.permission_checker = permission_checker
        self.max_output_length = settings.max_tool_output_length

    async def execute(
        self,
        tool_call: ToolUseBlock,
        ask_callback: Any = None,
    ) -> str:
        """
        执行工具调用

        Args:
            tool_call: 工具调用信息
            ask_callback: 用户确认回调函数

        Returns:
            工具执行结果
        """
        tool_name = tool_call.name
        tool_input = tool_call.input
        tool_id = tool_call.id

        logger.info(
            "Executing tool",
            extra_data={
                "tool_name": tool_name,
                "tool_id": tool_id,
            },
        )

        # 检查工具是否存在
        tool = self.registry.get(tool_name)
        if tool is None:
            error_msg = f"Error: Tool '{tool_name}' not found"
            logger.warning(error_msg)
            return error_msg

        # 权限检查
        if self.permission_checker:
            perm_result = self.permission_checker.check(tool_name, tool_input)

            if perm_result == PermissionResult.DENY:
                error_msg = f"Error: Tool '{tool_name}' is not allowed"
                logger.warning(
                    "Tool denied by permission",
                    extra_data={"tool_name": tool_name},
                )
                return error_msg

            if perm_result == PermissionResult.ASK and ask_callback:
                confirmed = await ask_callback(tool_name, tool_input)
                if not confirmed:
                    return f"Error: User denied tool '{tool_name}' execution"

        # 执行工具
        try:
            result = await asyncio.wait_for(
                tool.execute(**tool_input),
                timeout=self.timeout,
            )

            # 截断过长输出
            if len(result) > self.max_output_length:
                result = (
                    result[: self.max_output_length]
                    + f"\n... (truncated, total {len(result)} chars)"
                )
                logger.debug(
                    "Tool output truncated",
                    extra_data={"tool_name": tool_name},
                )

            logger.info(
                "Tool executed successfully",
                extra_data={
                    "tool_name": tool_name,
                    "result_length": len(result),
                },
            )

            return result

        except asyncio.TimeoutError:
            error_msg = f"Error: Tool '{tool_name}' execution timed out after {self.timeout}s"
            logger.error(
                "Tool execution timeout",
                extra_data={"tool_name": tool_name, "timeout": self.timeout},
            )
            return error_msg

        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            logger.error(
                "Tool execution error",
                extra_data={
                    "tool_name": tool_name,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
            )
            return error_msg

    async def execute_batch(
        self,
        tool_calls: list[ToolUseBlock],
        ask_callback: Any = None,
    ) -> list[tuple[str, str]]:
        """
        批量执行工具调用

        Args:
            tool_calls: 工具调用列表
            ask_callback: 用户确认回调函数

        Returns:
            [(tool_use_id, result), ...] 列表
        """
        tasks = [
            self.execute(tool_call, ask_callback)
            for tool_call in tool_calls
        ]
        results = await asyncio.gather(*tasks)

        return [
            (tool_call.id, result)
            for tool_call, result in zip(tool_calls, results)
        ]
