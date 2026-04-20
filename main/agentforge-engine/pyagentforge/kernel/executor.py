"""
工具执行器

负责执行工具调用并返回结果
"""

import asyncio
import logging
import traceback
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pyagentforge.kernel.message import ToolUseBlock

# 导入完整的 ToolRegistry 实现（修复双重实现问题）
from pyagentforge.tools.registry import ToolRegistry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# 权限检查结果枚举
class PermissionResult:
    """权限检查结果"""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionChecker:
    """简单的权限检查器"""

    def __init__(
        self,
        allowed_tools: set[str] | None = None,
        denied_tools: set[str] | None = None,
        ask_tools: set[str] | None = None,
    ):
        self.allowed_tools = allowed_tools or set()
        self.denied_tools = denied_tools or set()
        self.ask_tools = ask_tools or set()

    def check(self, tool_name: str, _tool_input: dict) -> str:
        """检查工具权限"""
        if tool_name in self.denied_tools:
            return PermissionResult.DENY
        if tool_name in self.ask_tools:
            return PermissionResult.ASK
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return PermissionResult.DENY
        return PermissionResult.ALLOW


# ToolRegistry 已从 pyagentforge.tools.registry 导入
# 移除本地重复实现（修复双重实现 bug）


class ToolExecutor:
    """工具执行器"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        timeout: int = 120,
        permission_checker: PermissionChecker | None = None,
        max_output_length: int = 50000,
    ) -> None:
        """
        初始化工具执行器

        Args:
            tool_registry: 工具注册表
            timeout: 执行超时时间(秒)
            permission_checker: 权限检查器
            max_output_length: 最大输出长度
        """
        self.registry = tool_registry
        self.timeout = timeout
        self.permission_checker = permission_checker
        self.max_output_length = max_output_length

    async def execute(
        self,
        tool_call: ToolUseBlock,
        ask_callback: Callable[[str, dict], Any] | None = None,
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

        logger.info(f"Executing tool: {tool_name} (id={tool_id})")

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
                logger.warning(f"Tool denied by permission: {tool_name}")
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
                logger.debug(f"Tool output truncated: {tool_name}")

            logger.info(f"Tool executed successfully: {tool_name}, result_len={len(result)}")

            return result

        except TimeoutError:
            error_msg = f"Error: Tool '{tool_name}' execution timed out after {self.timeout}s"
            logger.error(f"Tool execution timeout: {tool_name}, timeout={self.timeout}")
            return error_msg

        except Exception as e:
            error_msg = f"Error executing tool '{tool_name}': {str(e)}"
            logger.error(
                f"Tool execution error: {tool_name}, error={str(e)}\n{traceback.format_exc()}"
            )
            return error_msg

    async def execute_batch(
        self,
        tool_calls: list[ToolUseBlock],
        ask_callback: Callable[[str, dict], Any] | None = None,
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
