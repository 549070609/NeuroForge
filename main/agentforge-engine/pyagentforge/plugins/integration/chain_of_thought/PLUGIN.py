"""
思维链系统插件

提供结构化思考过程指导 Agent 解决问题。

Phase 2 增强:
- 与 Plan 工具深度集成
- 执行过程中的约束验证
- 阶段转换跟踪
"""

from pathlib import Path
from typing import Any
import re

from pyagentforge.plugin.base import Plugin, PluginType
from pyagentforge.plugin.hooks import HookType, HookDecision
from pyagentforge.utils.logging import get_logger

from .cot_manager import ChainOfThoughtManager
from .cot_tools import (
    LoadCoTTool,
    UpdateCoTTool,
    ValidatePlanTool,
    GetCoTInfoTool,
    CreateCoTTool,
    AnalyzeCoTTool,
    ImproveCoTTool,
    ReflectCoTTool,
    StatsCoTTool,
    # Phase 4 工具
    VersionCoTTool,
    CombineCoTTool,
    ExportCoTTool,
    ImportCoTTool,
    ListAllCoTTool,
    DeleteCoTTool,
    CloneCoTTool,
)
from .models import ConstraintType

logger = get_logger(__name__)


class ChainOfThoughtPlugin(Plugin):
    """思维链系统插件"""

    def __init__(self):
        super().__init__()

        self.metadata = self.PluginMetadata(
            id="chain_of_thought",
            name="Chain of Thought System",
            version="4.0.0",
            type=PluginType.INTEGRATION,
            description="Structured thinking process for enhanced problem solving",
            author="PyAgentForge Team",
            priority=100,  # 较高优先级，确保在其他插件之前加载
        )

        self._cot_manager: ChainOfThoughtManager | None = None
        self._session_id: str = ""
        self._current_phase_index: int = 0
        self._phase_history: list[dict[str, Any]] = []

    async def on_activate(self) -> None:
        """激活插件"""
        # 确定模板和 Agent CoT 目录
        plugin_dir = Path(__file__).parent
        templates_dir = plugin_dir / "cot_templates"
        agent_cot_dir = plugin_dir / "agent_cot"

        # 创建管理器
        self._cot_manager = ChainOfThoughtManager(
            templates_dir=templates_dir,
            agent_cot_dir=agent_cot_dir,
        )

        # 注册工具
        tools = [
            LoadCoTTool(),
            UpdateCoTTool(),
            ValidatePlanTool(),
            GetCoTInfoTool(),
            CreateCoTTool(),
            # Phase 3 工具
            AnalyzeCoTTool(),
            ImproveCoTTool(),
            ReflectCoTTool(),
            StatsCoTTool(),
            # Phase 4 工具
            VersionCoTTool(),
            CombineCoTTool(),
            ExportCoTTool(),
            ImportCoTTool(),
            ListAllCoTTool(),
            DeleteCoTTool(),
            CloneCoTTool(),
        ]

        for tool in tools:
            self.register_tool(tool)

        logger.info("Chain of Thought System v4.0 activated")

    async def on_deactivate(self) -> None:
        """停用插件"""
        logger.info("Chain of Thought System deactivated")

    def get_context(self) -> dict[str, Any]:
        """获取插件上下文"""
        return {
            "cot_manager": self._cot_manager,
        }

    # ============ 钩子实现 ============

    async def on_engine_start(self, engine) -> None:
        """引擎启动时"""
        self._session_id = engine.session_id
        self._current_phase_index = 0
        self._phase_history = []

        # 开始执行跟踪
        if self._cot_manager:
            trace = self._cot_manager.start_execution(self._session_id)
            if trace:
                logger.info(f"Started CoT execution trace for session {self._session_id}")

    async def on_engine_stop(self, engine) -> None:
        """引擎停止时"""
        if self._cot_manager:
            trace = self._cot_manager.get_execution_trace()
            if trace and not trace.end_time:
                # 计算执行时间
                success = len(trace.violations) == 0 or all(
                    v.constraint_type != ConstraintType.HARD
                    for v in trace.violations
                )

                reflection = self._generate_reflection()
                self._cot_manager.complete_execution(
                    success=success,
                    reflection=reflection,
                )

                logger.info(f"CoT execution completed: success={success}")

    async def on_before_llm_call(self, messages: list) -> list | None:
        """LLM 调用前 - 注入思维链指导和阶段提示"""
        if not self._cot_manager:
            return None

        current_cot = self._cot_manager.get_current_cot()
        if not current_cot:
            return None

        # 生成思维链指导文本
        guidance = self._cot_manager.generate_system_prompt_extension()
        if not guidance:
            return None

        # 获取当前阶段提示
        phase_prompt = self._get_current_phase_prompt()

        # 构建完整指导
        full_guidance = guidance
        if phase_prompt:
            full_guidance += f"\n\n## 当前阶段\n{phase_prompt}"

        # 修改第一条系统消息或添加新的系统消息
        modified = False
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                # 检查是否已经注入过
                existing = msg.get("content", "")
                if "## 思维链指导:" not in existing:
                    messages[i]["content"] = existing + "\n" + full_guidance
                    modified = True
                break

        if not modified:
            # 添加新的系统消息（放在开头）
            messages.insert(0, {
                "role": "system",
                "content": full_guidance,
            })

        logger.debug("Injected CoT guidance into system prompt")
        return messages

    async def on_task_complete(self, result: str) -> None:
        """任务完成时"""
        if not self._cot_manager:
            return

        # 生成反思
        reflection = self._generate_reflection_from_result(result)

        # 完成执行跟踪
        self._cot_manager.complete_execution(
            success=True,
            reflection=reflection,
        )

        logger.info("Task completed, CoT execution trace finalized")

    async def on_before_tool_call(self, tool_use) -> tuple[HookDecision, str] | None:
        """工具执行前 - 验证约束和跟踪阶段"""
        if not self._cot_manager:
            return None

        current_cot = self._cot_manager.get_current_cot()
        if not current_cot:
            return None

        tool_name = getattr(tool_use, "name", "")

        # 处理计划工具
        if tool_name in ["plan", "plan_exit", "plan_enter"]:
            return await self._handle_plan_tool(tool_use)

        # 处理任务创建工具
        if tool_name == "task_create":
            return await self._handle_task_create(tool_use)

        # 记录工具调用到阶段历史
        self._record_tool_call(tool_name, tool_use)

        return None

    async def on_after_tool_call(self, result: str, tool_use: Any = None) -> str | None:
        """工具执行后 - 记录阶段结果和检查阶段转换"""
        if not self._cot_manager:
            return None

        trace = self._cot_manager.get_execution_trace()
        if not trace:
            return None

        # 推断当前阶段
        current_phase = self._infer_current_phase(result)
        if current_phase:
            self._cot_manager.record_phase_result(current_phase, {
                "result_preview": result[:200] if result else "",
                "timestamp": self._get_timestamp(),
            })

            # 检查是否需要推进到下一阶段
            self._advance_phase_if_needed(current_phase)

        return None

    # ============ Phase 2 辅助方法 ============

    async def _handle_plan_tool(self, tool_use) -> tuple[HookDecision, str] | None:
        """处理计划工具调用"""
        tool_name = getattr(tool_use, "name", "")
        tool_input = getattr(tool_use, "input", {})

        if tool_name in ["plan_exit", "plan"] and "plan" in tool_input:
            # 提取计划步骤
            plan_data = tool_input.get("plan", [])

            # 转换为标准格式
            if isinstance(plan_data, list):
                if all(isinstance(step, str) for step in plan_data):
                    plan_steps = [{"description": step} for step in plan_data]
                else:
                    plan_steps = plan_data
            else:
                plan_steps = []

            # 验证计划
            is_valid, violations = self._cot_manager.validate_plan_against_cot(plan_steps)

            # 记录违反
            for v in violations:
                self._cot_manager.record_violation(v)

            # 记录计划
            self._cot_manager.record_plan(plan_steps)

            # 如果有硬约束违反，阻止执行
            if not is_valid:
                error_msg = self._format_violation_error(violations)
                logger.warning(f"Plan blocked due to constraint violations: {len(violations)}")
                return (HookDecision.BLOCK, error_msg)

            logger.info(f"Plan validated: {len(plan_steps)} steps, {len(violations)} warnings")

        return None

    async def _handle_task_create(self, tool_use) -> tuple[HookDecision, str] | None:
        """处理任务创建工具调用"""
        # 任务创建时可以验证是否符合思维链规划
        # 目前简单通过，未来可以添加更多验证
        return None

    def _get_current_phase_prompt(self) -> str | None:
        """获取当前阶段的提示"""
        if not self._cot_manager:
            return None

        current_cot = self._cot_manager.get_current_cot()
        if not current_cot:
            return None

        phases = current_cot.get_ordered_phases()
        if not phases:
            return None

        if self._current_phase_index < len(phases):
            phase = phases[self._current_phase_index]
            return f"**{phase.name}**\n{phase.prompt}"

        return None

    def _infer_current_phase(self, result: str) -> str | None:
        """从工具结果推断当前阶段"""
        if not self._cot_manager:
            return None

        current_cot = self._cot_manager.get_current_cot()
        if not current_cot:
            return None

        # 简单的关键词匹配
        result_lower = result.lower()

        phase_keywords = {
            "understand": ["理解", "问题", "需求", "understand", "problem", "require"],
            "analyze": ["分析", "分解", "analyze", "breakdown", "decompose"],
            "plan": ["计划", "步骤", "plan", "step", "approach"],
            "execute": ["执行", "实现", "execute", "implement", "run"],
            "reflect": ["反思", "验证", "总结", "reflect", "verify", "summary"],
            "reproduce": ["复现", "重现", "reproduce"],
            "localize": ["定位", "找到", "localize", "locate", "find"],
            "hypothesize": ["假设", "猜测", "hypothes", "guess", "assume"],
            "verify": ["验证", "确认", "verify", "confirm", "test"],
            "fix": ["修复", "改正", "fix", "repair", "patch"],
        }

        for phase in current_cot.phases:
            keywords = phase_keywords.get(phase.name.lower(), [])
            if any(kw in result_lower for kw in keywords):
                return phase.name

        return None

    def _advance_phase_if_needed(self, current_phase: str) -> None:
        """检查是否需要推进到下一阶段"""
        if not self._cot_manager:
            return

        current_cot = self._cot_manager.get_current_cot()
        if not current_cot:
            return

        phases = current_cot.get_ordered_phases()
        if not phases:
            return

        # 查找当前阶段
        for i, phase in enumerate(phases):
            if phase.name == current_phase and i > self._current_phase_index:
                self._current_phase_index = i
                logger.info(f"Advanced to phase: {phase.name}")
                break

    def _record_tool_call(self, tool_name: str, tool_use: Any) -> None:
        """记录工具调用"""
        self._phase_history.append({
            "tool": tool_name,
            "input": getattr(tool_use, "input", {}),
            "phase_index": self._current_phase_index,
            "timestamp": self._get_timestamp(),
        })

    def _format_violation_error(self, violations: list) -> str:
        """格式化约束违反错误"""
        lines = ["⚠️ 计划违反了思维链约束:\n"]

        for v in violations:
            if v.constraint_type == ConstraintType.HARD:
                icon = "❗"
            elif v.constraint_type == ConstraintType.SOFT:
                icon = "⚠️"
            else:
                icon = "📝"

            lines.append(f"{icon} [{v.phase_name}] {v.constraint_description}")
            if v.violation_details:
                lines.append(f"   详情: {v.violation_details}")
            lines.append("")

        lines.append("请修改计划以满足这些约束后再执行。")
        return "\n".join(lines)

    def _generate_reflection(self) -> str:
        """生成执行反思"""
        if not self._phase_history:
            return "No tool calls recorded"

        phase_counts = {}
        for record in self._phase_history:
            phase_idx = record.get("phase_index", 0)
            phase_counts[phase_idx] = phase_counts.get(phase_idx, 0) + 1

        reflection_parts = [
            f"Total tool calls: {len(self._phase_history)}",
            f"Phases visited: {len(phase_counts)}",
            f"Final phase index: {self._current_phase_index}",
        ]

        return "; ".join(reflection_parts)

    def _generate_reflection_from_result(self, result: str) -> str:
        """从结果生成反思"""
        reflection = self._generate_reflection()

        # 添加结果摘要
        result_preview = result[:100] if result else ""
        if result_preview:
            reflection += f"; Result: {result_preview}..."

        return reflection

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# 导出
__all__ = [
    "ChainOfThoughtPlugin",
    "ChainOfThoughtManager",
]
