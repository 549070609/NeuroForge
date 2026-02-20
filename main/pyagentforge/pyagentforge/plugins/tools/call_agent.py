"""
Call Agent Tool

v4.0: 子代理调用工具

允许主代理调用其他类型的代理。
"""

from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CallAgentTool(BaseTool):
    """
    调用代理工具

    调用指定类型的代理执行任务。
    """

    name = "call_agent"
    description = "Call another agent to perform a specific task"
    parameters_schema = {
        "type": "object",
        "properties": {
            "agent_type": {
                "type": "string",
                "description": "The type of agent to call (e.g., 'explore', 'plan', 'code')",
                "enum": ["explore", "plan", "code", "review", "librarian", "oracle"],
            },
            "prompt": {
                "type": "string",
                "description": "The task prompt to send to the agent",
            },
            "wait_for_completion": {
                "type": "boolean",
                "description": "Wait for the agent to complete (default: true)",
                "default": True,
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds to wait for completion (default: 120)",
                "default": 120,
            },
            "background": {
                "type": "boolean",
                "description": "Run agent in background (default: false)",
                "default": False,
            },
        },
        "required": ["agent_type", "prompt"],
    }
    timeout = 180
    risk_level = "medium"

    async def execute(
        self,
        agent_type: str,
        prompt: str,
        wait_for_completion: bool = True,
        timeout: int = 120,
        background: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        执行工具

        Args:
            agent_type: 代理类型
            prompt: 任务提示
            wait_for_completion: 是否等待完成
            timeout: 超时秒数
            background: 是否在后台运行

        Returns:
            代理执行结果
        """
        # 获取必要的组件
        engine_factory = kwargs.get("engine_factory")
        background_manager = kwargs.get("background_manager")
        session_id = kwargs.get("session_id", "default")

        if not engine_factory:
            return "Error: Engine factory not available"

        # 后台模式
        if background:
            if not background_manager:
                return "Error: Background manager not available for background execution"

            # 启动后台任务
            task = await background_manager.launch(
                agent_type=agent_type,
                prompt=prompt,
                session_id=session_id,
                metadata={"parent_call": "call_agent_tool"},
            )

            return f"Started background task {task.id} with agent '{agent_type}'"

        # 同步模式
        try:
            # 创建引擎
            engine = engine_factory(agent_type)

            if not engine:
                return f"Error: Failed to create engine for agent '{agent_type}'"

            logger.info(
                f"Calling agent: {agent_type}",
                extra_data={"session_id": session_id, "wait": wait_for_completion},
            )

            # 执行任务
            if wait_for_completion:
                result = await engine.run(prompt)

                return f"""Agent '{agent_type}' completed successfully.

Result:
{result}
"""
            else:
                # 异步执行但不等待
                import asyncio

                asyncio.create_task(engine.run(prompt))

                return f"Agent '{agent_type}' started (not waiting for completion)"

        except asyncio.TimeoutError:
            return f"Error: Agent '{agent_type}' timed out after {timeout} seconds"

        except Exception as e:
            logger.error(f"Error calling agent '{agent_type}': {e}")
            return f"Error: Failed to call agent '{agent_type}': {str(e)}"


# 导出
__all__ = ["CallAgentTool"]
