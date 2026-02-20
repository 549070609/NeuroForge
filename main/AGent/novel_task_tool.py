"""
小说创作子Agent工具
支持总编辑自动调度专业设定团队
"""
import asyncio
from typing import Any, Optional
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.context import ContextManager
from pyagentforge.tools.base import BaseTool
from pyagentforge.kernel.executor import ToolRegistry

from subagent_types import NOVEL_SUBAGENT_TYPES


class NovelTaskTool(BaseTool):
    """小说创作子Agent工具 - 总编辑调用专业设定团队"""

    name = "Task"
    description = "调用专业子Agent完成特定创作任务"
    timeout = 300
    risk_level = "medium"

    def __init__(
        self,
        provider: Any,
        tool_registry: ToolRegistry,
        current_depth: int = 0,
        max_depth: int = 2,
    ):
        self.provider = provider
        self.tool_registry = tool_registry
        self.current_depth = current_depth
        self.max_depth = max_depth

    async def execute(
        self,
        subagent_type: str,
        prompt: str,
    ) -> str:
        """
        调用子Agent执行任务

        Args:
            subagent_type: 子Agent类型
                - world-builder: 世界构建师
                - character-designer: 人物设定师
                - theme-planner: 主题策划师
                - style-designer: 风格设定师
                - audience-analyzer: 读者分析师
                - plot-architect: 情节架构师
            prompt: 具体任务描述
        """
        # 深度检查
        if self.current_depth >= self.max_depth:
            return "错误：已达到最大子Agent嵌套深度"

        # 获取子Agent配置
        config = NOVEL_SUBAGENT_TYPES.get(subagent_type)
        if not config:
            available = ", ".join(NOVEL_SUBAGENT_TYPES.keys())
            return f"错误：未知的子Agent类型 '{subagent_type}'。可用类型: {available}"

        # 创建隔离上下文
        sub_context = ContextManager(system_prompt=config["system_prompt"])

        # 过滤工具
        sub_tools = self._filter_tools(config["tools"])

        # 递归创建Task工具（深度+1），允许子Agent再调用其他子Agent
        if self.current_depth + 1 < self.max_depth:
            sub_tools.register(NovelTaskTool(
                provider=self.provider,
                tool_registry=sub_tools,
                current_depth=self.current_depth + 1,
                max_depth=self.max_depth,
            ))

        # 创建子Agent引擎
        sub_engine = AgentEngine(
            provider=self.provider,
            tool_registry=sub_tools,
            config=AgentConfig(system_prompt=config["system_prompt"]),
            context=sub_context,
        )

        # 执行
        result = await sub_engine.run(prompt)
        return f"<{subagent_type}结果>\n{result}\n</{subagent_type}结果>"

    def _filter_tools(self, allowed: list[str]) -> ToolRegistry:
        """过滤工具，只保留允许的工具"""
        new_registry = ToolRegistry()
        for tool_name in allowed:
            tool = self.tool_registry.get(tool_name)
            if tool:
                new_registry.register(tool)
        return new_registry

    @classmethod
    def get_schema(cls) -> dict:
        """返回工具的 Anthropic schema"""
        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "subagent_type": {
                        "type": "string",
                        "enum": list(NOVEL_SUBAGENT_TYPES.keys()),
                        "description": "子Agent类型"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "具体任务描述"
                    }
                },
                "required": ["subagent_type", "prompt"]
            }
        }


class ParallelTaskTool(BaseTool):
    """并行调用多个子Agent"""

    name = "ParallelTask"
    description = "并行调用多个专业子Agent，适用于需要多个专业设定的场景"
    timeout = 600

    def __init__(
        self,
        provider: Any,
        tool_registry: ToolRegistry,
        current_depth: int = 0,
        max_depth: int = 2,
    ):
        self.provider = provider
        self.tool_registry = tool_registry
        self.current_depth = current_depth
        self.max_depth = max_depth

    async def execute(
        self,
        tasks: list[dict],
    ) -> str:
        """
        并行调用多个子Agent

        Args:
            tasks: 任务列表，每个任务包含 subagent_type 和 prompt
        """
        if self.current_depth >= self.max_depth:
            return "错误：已达到最大子Agent嵌套深度"

        async def run_single_task(task: dict) -> str:
            """执行单个任务"""
            subagent_type = task.get("subagent_type")
            prompt = task.get("prompt")
            if not subagent_type or not prompt:
                return f"错误：任务缺少必要字段"

            task_tool = NovelTaskTool(
                provider=self.provider,
                tool_registry=self.tool_registry,
                current_depth=self.current_depth,
                max_depth=self.max_depth,
            )
            return await task_tool.execute(subagent_type, prompt)

        # 并行执行所有任务
        results = await asyncio.gather(*[run_single_task(task) for task in tasks])

        return "\n\n---\n\n".join(results)

    @classmethod
    def get_schema(cls) -> dict:
        """返回工具的 Anthropic schema"""
        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subagent_type": {
                                    "type": "string",
                                    "enum": list(NOVEL_SUBAGENT_TYPES.keys()),
                                    "description": "子Agent类型"
                                },
                                "prompt": {
                                    "type": "string",
                                    "description": "具体任务描述"
                                }
                            },
                            "required": ["subagent_type", "prompt"]
                        },
                        "description": "任务列表"
                    }
                },
                "required": ["tasks"]
            }
        }
