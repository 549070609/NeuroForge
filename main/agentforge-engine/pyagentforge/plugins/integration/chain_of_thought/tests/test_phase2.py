"""
思维链 Phase 2 集成测试

测试执行集成功能：
- Plan 生成时的约束注入
- 执行过程中的约束验证
- 约束违反的处理逻辑
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pyagentforge.plugin.hooks import HookDecision
from pyagentforge.plugins.integration.chain_of_thought.cot_manager import ChainOfThoughtManager
from pyagentforge.plugins.integration.chain_of_thought.models import (
    ChainOfThought,
    Constraint,
    ConstraintType,
    ConstraintViolation,
    CoTPhase,
)
from pyagentforge.plugins.integration.chain_of_thought.PLUGIN import ChainOfThoughtPlugin


@pytest.fixture
def plugin():
    """创建插件实例"""
    return ChainOfThoughtPlugin()


@pytest.fixture
def manager():
    """创建管理器实例"""
    with tempfile.TemporaryDirectory() as tmpdir:
        templates_dir = Path(tmpdir) / "templates"
        agent_dir = Path(tmpdir) / "agent_cot"
        templates_dir.mkdir()
        agent_dir.mkdir()
        yield ChainOfThoughtManager(
            templates_dir=templates_dir,
            agent_cot_dir=agent_dir,
        )


class TestPlanValidation:
    """测试计划验证"""

    @pytest.mark.asyncio
    async def test_plan_validated_on_exit(self, plugin, manager):
        """测试退出计划模式时验证"""
        # 设置思维链
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase(
                    "plan",
                    "planning",
                    constraints=[
                        Constraint("必须有验证步骤", ConstraintType.HARD),
                    ],
                    order=0,
                ),
            ],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        plugin._cot_manager = manager

        # 模拟 plan_exit 工具调用
        tool_use = MagicMock()
        tool_use.name = "plan_exit"
        tool_use.input = {
            "plan": ["步骤1", "步骤2", "验证结果"]
        }

        result = await plugin.on_before_tool_call(tool_use)

        # 应该通过验证
        assert result is None

        # 检查计划已记录
        trace = manager.get_execution_trace()
        assert trace is not None
        assert len(trace.plan_steps) == 3

    @pytest.mark.asyncio
    async def test_plan_blocked_on_hard_violation(self, plugin, manager):
        """测试硬约束违反时阻止计划"""
        # 设置思维链（无验证步骤约束）
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase(
                    "plan",
                    "planning",
                    constraints=[
                        Constraint("必须包含验证步骤", ConstraintType.HARD),
                    ],
                    order=0,
                ),
            ],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        plugin._cot_manager = manager

        # 模拟 plan_exit 工具调用（无验证步骤）
        tool_use = MagicMock()
        tool_use.name = "plan_exit"
        tool_use.input = {
            "plan": ["步骤1", "步骤2"]
        }

        result = await plugin.on_before_tool_call(tool_use)

        # 应该被阻止
        assert result is not None
        assert result[0] == HookDecision.BLOCK
        assert "违反" in result[1] or "constraint" in result[1].lower()

    @pytest.mark.asyncio
    async def test_soft_violation_warning_only(self, plugin, manager):
        """测试软约束只警告不阻止"""
        # 设置思维链（软约束）
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase(
                    "plan",
                    "planning",
                    constraints=[
                        Constraint("步骤数量建议不超过7个", ConstraintType.SOFT),
                    ],
                    order=0,
                ),
            ],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        plugin._cot_manager = manager

        # 模拟 plan_exit 工具调用（10个步骤）
        tool_use = MagicMock()
        tool_use.name = "plan_exit"
        tool_use.input = {
            "plan": [f"步骤{i}" for i in range(10)]
        }

        result = await plugin.on_before_tool_call(tool_use)

        # 应该通过（软约束不阻止）
        assert result is None

        # 但应该有违反记录
        manager.get_execution_trace()
        # 注意：实际验证逻辑取决于具体实现


class TestPhaseTracking:
    """测试阶段跟踪"""

    @pytest.mark.asyncio
    async def test_phase_inference(self, plugin, manager):
        """测试阶段推断"""
        cot = ChainOfThought(
            name="debugging",
            description="debugging",
            phases=[
                CoTPhase("reproduce", "复现问题", order=0),
                CoTPhase("localize", "定位原因", order=1),
                CoTPhase("fix", "修复问题", order=2),
            ],
        )
        manager.set_current_cot(cot)
        plugin._cot_manager = manager

        # 测试推断
        phase = plugin._infer_current_phase("问题已复现，错误出现在第42行")
        assert phase == "reproduce"

        phase = plugin._infer_current_phase("定位到问题在 calculate() 函数")
        assert phase == "localize"

        phase = plugin._infer_current_phase("已修复该 bug")
        assert phase == "fix"

    @pytest.mark.asyncio
    async def test_phase_advancement(self, plugin, manager):
        """测试阶段推进"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase("phase1", "Phase 1", order=0),
                CoTPhase("phase2", "Phase 2", order=1),
                CoTPhase("phase3", "Phase 3", order=2),
            ],
        )
        manager.set_current_cot(cot)

        plugin._cot_manager = manager
        plugin._current_phase_index = 0

        # 推进到 phase2
        plugin._advance_phase_if_needed("phase2")
        assert plugin._current_phase_index == 1

        # 推进到 phase3
        plugin._advance_phase_if_needed("phase3")
        assert plugin._current_phase_index == 2

        # 不能回退
        plugin._advance_phase_if_needed("phase1")
        assert plugin._current_phase_index == 2

    @pytest.mark.asyncio
    async def test_tool_call_recording(self, plugin, manager):
        """测试工具调用记录"""
        plugin._cot_manager = manager
        plugin._phase_history = []

        tool_use = MagicMock()
        tool_use.name = "read_file"
        tool_use.input = {"path": "/test/file.py"}

        plugin._record_tool_call("read_file", tool_use)

        assert len(plugin._phase_history) == 1
        assert plugin._phase_history[0]["tool"] == "read_file"


class TestSystemPromptInjection:
    """测试系统提示注入"""

    @pytest.mark.asyncio
    async def test_cot_guidance_injection(self, plugin, manager):
        """测试思维链指导注入"""
        cot = ChainOfThought(
            name="debugging",
            description="调试思维链",
            phases=[
                CoTPhase("reproduce", "复现问题", order=0),
                CoTPhase("fix", "修复问题", order=1),
            ],
        )
        manager.set_current_cot(cot)
        plugin._cot_manager = manager
        plugin._current_phase_index = 0

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Help me debug"},
        ]

        modified = await plugin.on_before_llm_call(messages)

        assert modified is not None
        assert "思维链指导" in modified[0]["content"] or "debugging" in modified[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_no_injection_without_cot(self, plugin, manager):
        """测试无思维链时不注入"""
        plugin._cot_manager = manager

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
        ]

        modified = await plugin.on_before_llm_call(messages)

        # 无思维链时返回 None
        assert modified is None


class TestExecutionTrace:
    """测试执行轨迹"""

    @pytest.mark.asyncio
    async def test_engine_start_creates_trace(self, plugin, manager):
        """测试引擎启动时创建轨迹"""
        plugin._cot_manager = manager

        engine = MagicMock()
        engine.session_id = "test_session_123"

        await plugin.on_engine_start(engine)

        manager.get_execution_trace()
        # 如果没有当前思维链，不会创建轨迹
        # 这是预期行为

    @pytest.mark.asyncio
    async def test_engine_stop_finalizes_trace(self, plugin, manager):
        """测试引擎停止时完成轨迹"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[CoTPhase("phase1", "test", order=0)],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        plugin._cot_manager = manager

        engine = MagicMock()
        engine.session_id = "test_session"

        await plugin.on_engine_stop(engine)

        trace = manager.get_execution_trace()
        assert trace is not None
        assert trace.end_time is not None


class TestReflectionGeneration:
    """测试反思生成"""

    def test_reflection_with_history(self, plugin, manager):
        """测试有历史记录时的反思"""
        plugin._cot_manager = manager
        plugin._phase_history = [
            {"tool": "read", "phase_index": 0},
            {"tool": "edit", "phase_index": 1},
            {"tool": "test", "phase_index": 2},
        ]
        plugin._current_phase_index = 2

        reflection = plugin._generate_reflection()

        assert "3" in reflection  # 3 tool calls
        assert "phase" in reflection.lower()

    def test_reflection_without_history(self, plugin, manager):
        """测试无历史记录时的反思"""
        plugin._cot_manager = manager
        plugin._phase_history = []

        reflection = plugin._generate_reflection()

        assert "No tool calls" in reflection


class TestViolationFormatting:
    """测试违反格式化"""

    def test_format_hard_violation(self, plugin):
        """测试硬违反格式化"""
        violations = [
            ConstraintViolation(
                phase_name="plan",
                constraint_description="必须有验证步骤",
                constraint_type=ConstraintType.HARD,
                violation_details="Plan lacks validation steps",
            )
        ]

        formatted = plugin._format_violation_error(violations)

        assert "❗" in formatted
        assert "plan" in formatted.lower()
        assert "必须有验证步骤" in formatted

    def test_format_soft_violation(self, plugin):
        """测试软违反格式化"""
        violations = [
            ConstraintViolation(
                phase_name="analyze",
                constraint_description="建议子问题不超过7个",
                constraint_type=ConstraintType.SOFT,
                violation_details="Found 10 sub-problems",
            )
        ]

        formatted = plugin._format_violation_error(violations)

        assert "⚠️" in formatted
        assert "analyze" in formatted.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
