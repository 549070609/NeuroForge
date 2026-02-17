"""
Plan 工具

进入和退出计划模式
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class PlanMode(Enum):
    """计划模式状态"""

    INACTIVE = "inactive"
    ACTIVE = "active"


class PlanState(BaseModel):
    """计划状态"""

    mode: PlanMode = PlanMode.INACTIVE
    plan: list[str] = Field(default_factory=list)
    current_step: int = 0
    notes: list[str] = Field(default_factory=list)


# 全局计划状态
_plan_state = PlanState()


class PlanEnterTool(BaseTool):
    """PlanEnter 工具 - 进入计划模式"""

    name = "plan_enter"
    description = """进入计划模式。

在计划模式中:
- Agent 只分析不执行
- 生成编号计划
- 不修改文件
- 专注于规划

适合复杂任务的规划阶段。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "objective": {
                "type": "string",
                "description": "计划目标描述",
            },
        },
        "required": ["objective"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(self, objective: str) -> str:
        """进入计划模式"""
        logger.info("Entering plan mode", extra_data={"objective": objective[:100]})

        global _plan_state
        _plan_state.mode = PlanMode.ACTIVE
        _plan_state.plan = []
        _plan_state.current_step = 0
        _plan_state.notes = []

        return f"""=== PLAN MODE ACTIVATED ===

Objective: {objective}

In plan mode, I will:
1. Analyze the requirements
2. Explore relevant files
3. Generate a numbered plan
4. NOT modify any files

When ready, use plan_exit to finish planning.

Plan mode is now active. What would you like me to analyze?"""


class PlanExitTool(BaseTool):
    """PlanExit 工具 - 退出计划模式"""

    name = "plan_exit"
    description = """退出计划模式并返回计划。

完成规划后调用此工具:
- 返回生成的计划
- 恢复正常执行模式
- 可以开始实现
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "plan": {
                "type": "array",
                "description": "计划步骤列表",
                "items": {"type": "string"},
            },
            "summary": {
                "type": "string",
                "description": "计划摘要",
            },
        },
        "required": ["plan"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        plan: list[str],
        summary: str | None = None,
    ) -> str:
        """退出计划模式"""
        logger.info("Exiting plan mode", extra_data={"steps": len(plan)})

        global _plan_state
        _plan_state.mode = PlanMode.INACTIVE
        _plan_state.plan = plan
        _plan_state.current_step = 0

        output = ["=== PLAN MODE EXITED ===", ""]

        if summary:
            output.append(f"Summary: {summary}")
            output.append("")

        output.append("## Implementation Plan")
        output.append("")

        for i, step in enumerate(plan, 1):
            output.append(f"{i}. {step}")

        output.append("")
        output.append("---")
        output.append("Plan mode deactivated. Ready to implement.")

        return "\n".join(output)


class PlanTool(BaseTool):
    """Plan 工具 - 综合计划工具"""

    name = "plan"
    description = """计划模式管理工具。

操作:
- enter: 进入计划模式 (只分析不执行)
- exit: 退出计划模式并返回计划
- status: 查看当前计划状态
- add_step: 添加计划步骤
- update_step: 更新计划步骤
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["enter", "exit", "status", "add_step", "update_step"],
                "description": "操作类型",
            },
            "objective": {
                "type": "string",
                "description": "计划目标 (enter 时使用)",
            },
            "plan": {
                "type": "array",
                "items": {"type": "string"},
                "description": "计划步骤列表 (exit 时使用)",
            },
            "step_index": {
                "type": "integer",
                "description": "步骤索引 (update_step 时使用)",
            },
            "step_content": {
                "type": "string",
                "description": "步骤内容 (add_step/update_step 时使用)",
            },
            "note": {
                "type": "string",
                "description": "备注",
            },
        },
        "required": ["action"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        action: str,
        objective: str | None = None,
        plan: list[str] | None = None,
        step_index: int | None = None,
        step_content: str | None = None,
        note: str | None = None,
    ) -> str:
        """执行计划操作"""
        global _plan_state

        if action == "enter":
            if not objective:
                return "Error: objective is required for 'enter' action"

            _plan_state.mode = PlanMode.ACTIVE
            _plan_state.plan = []
            _plan_state.current_step = 0
            _plan_state.notes = []

            return f"""=== PLAN MODE ACTIVATED ===

Objective: {objective}

In plan mode:
- Analyze only, no execution
- Generate numbered plan
- Do NOT modify files

Use 'plan exit' when ready."""

        elif action == "exit":
            if not plan:
                return "Error: plan is required for 'exit' action"

            _plan_state.mode = PlanMode.INACTIVE
            _plan_state.plan = plan
            _plan_state.current_step = 0

            lines = ["=== PLAN COMPLETE ===", ""]
            for i, step in enumerate(plan, 1):
                lines.append(f"{i}. {step}")
            lines.append("")
            lines.append("Ready to implement.")

            return "\n".join(lines)

        elif action == "status":
            mode_str = "ACTIVE" if _plan_state.mode == PlanMode.ACTIVE else "INACTIVE"
            lines = [
                f"Plan Mode: {mode_str}",
                f"Steps: {len(_plan_state.plan)}",
                "",
            ]

            if _plan_state.plan:
                lines.append("Current Plan:")
                for i, step in enumerate(_plan_state.plan, 1):
                    marker = "→" if i == _plan_state.current_step + 1 else " "
                    lines.append(f"  {marker} {i}. {step}")

            return "\n".join(lines)

        elif action == "add_step":
            if not step_content:
                return "Error: step_content is required for 'add_step' action"

            _plan_state.plan.append(step_content)
            if note:
                _plan_state.notes.append(note)

            return f"Added step {len(_plan_state.plan)}: {step_content}"

        elif action == "update_step":
            if step_index is None or not step_content:
                return "Error: step_index and step_content are required for 'update_step' action"

            if step_index < 1 or step_index > len(_plan_state.plan):
                return f"Error: Invalid step_index {step_index}"

            old_content = _plan_state.plan[step_index - 1]
            _plan_state.plan[step_index - 1] = step_content

            return f"Updated step {step_index}:\n  From: {old_content}\n  To: {step_content}"

        else:
            return f"Error: Unknown action '{action}'"


def get_plan_state() -> PlanState:
    """获取当前计划状态"""
    return _plan_state


def is_plan_mode() -> bool:
    """检查是否在计划模式"""
    return _plan_state.mode == PlanMode.ACTIVE
