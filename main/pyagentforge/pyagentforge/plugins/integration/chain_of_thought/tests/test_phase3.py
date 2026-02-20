"""
思维链 Phase 3 反思更新测试

测试反思、分析和改进功能：
- 执行轨迹分析
- 自动更新思维链
- 生成改进版本
- 统计信息
"""

import pytest
from pathlib import Path
import tempfile

from pyagentforge.plugins.integration.chain_of_thought.cot_manager import ChainOfThoughtManager
from pyagentforge.plugins.integration.chain_of_thought.models import (
    ChainOfThought,
    CoTPhase,
    Constraint,
    ConstraintType,
    ConstraintViolation,
)
from pyagentforge.plugins.integration.chain_of_thought.cot_tools import (
    AnalyzeCoTTool,
    ImproveCoTTool,
    ReflectCoTTool,
    StatsCoTTool,
)


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


class TestExecutionAnalysis:
    """测试执行分析"""

    def test_analyze_empty_trace(self, manager):
        """测试无执行轨迹时的分析"""
        analysis = manager.analyze_and_update_from_trace()

        assert "error" in analysis

    def test_analyze_successful_execution(self, manager):
        """测试成功执行的分析"""
        # 创建思维链
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase("phase1", "First", order=0),
                CoTPhase("phase2", "Second", order=1),
            ],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        # 记录阶段结果
        manager.record_phase_result("phase1", "done")
        manager.record_phase_result("phase2", "done")

        # 成功完成
        manager.complete_execution(True, "Success")

        # 分析
        analysis = manager.analyze_and_update_from_trace("deep")

        assert analysis["success"] is True
        assert analysis["violations_count"] == 0
        assert analysis["phases_executed"] == 2

    def test_analyze_with_violations(self, manager):
        """测试有违反的分析"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase(
                    "plan",
                    "Plan",
                    constraints=[Constraint("必须验证", ConstraintType.HARD)],
                    order=0,
                ),
            ],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        # 添加违反
        manager.record_violation(ConstraintViolation(
            phase_name="plan",
            constraint_description="必须验证",
            constraint_type=ConstraintType.HARD,
            violation_details="No validation step",
        ))

        manager.complete_execution(False, "Failed due to violation")

        # 分析
        analysis = manager.analyze_and_update_from_trace("deep")

        assert analysis["success"] is False
        assert analysis["hard_violations"] == 1
        assert len(analysis["suggestions"]) > 0

    def test_phase_insights(self, manager):
        """测试阶段洞察"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase(
                    "phase1",
                    "First",
                    constraints=[Constraint("约束1", ConstraintType.SOFT)],
                    order=0,
                ),
                CoTPhase("phase2", "Second", order=1),
            ],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        manager.record_phase_result("phase1", "done")
        manager.record_phase_result("phase2", "done")

        # phase1 有违反
        manager.record_violation(ConstraintViolation(
            phase_name="phase1",
            constraint_description="约束1",
            constraint_type=ConstraintType.SOFT,
            violation_details="Soft violation",
        ))

        manager.complete_execution(True, "Done with warnings")

        analysis = manager.analyze_and_update_from_trace()

        assert "phase1" in analysis["phase_insights"]
        assert analysis["phase_insights"]["phase1"]["had_violations"] is True


class TestCOTImprovement:
    """测试思维链改进"""

    def test_adjust_constraint_type(self, manager):
        """测试调整约束类型"""
        cot = ChainOfThought(
            name="test",
            description="test",
            version="1.0",
            phases=[
                CoTPhase(
                    "plan",
                    "Plan",
                    constraints=[Constraint("必须验证", ConstraintType.HARD)],
                    order=0,
                ),
            ],
        )
        manager.set_current_cot(cot)

        # 改进：将硬约束降为软约束
        improvements = {
            "adjust_constraints": [
                {
                    "phase": "plan",
                    "constraint_index": 0,
                    "new_type": "soft",
                }
            ]
        }

        improved = manager.generate_improved_cot(improvements)

        assert improved is not None
        assert improved.version == "1.1"
        assert improved.phases[0].constraints[0].constraint_type == ConstraintType.SOFT

    def test_add_new_phase(self, manager):
        """测试添加新阶段"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase("phase1", "First", order=0),
            ],
        )
        manager.set_current_cot(cot)

        improvements = {
            "add_phase": {
                "name": "review",
                "prompt": "Review the results",
                "order": 1,
                "is_required": False,
            }
        }

        improved = manager.generate_improved_cot(improvements)

        assert improved is not None
        assert len(improved.phases) == 2
        assert improved.get_phase("review") is not None

    def test_modify_prompt(self, manager):
        """测试修改提示"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase("execute", "Execute the plan", order=0),
            ],
        )
        manager.set_current_cot(cot)

        improvements = {
            "modify_prompt": [
                {
                    "phase": "execute",
                    "addition": "Always verify before proceeding",
                }
            ]
        }

        improved = manager.generate_improved_cot(improvements)

        assert improved is not None
        assert "Always verify" in improved.get_phase("execute").prompt

    def test_version_increment(self, manager):
        """测试版本号递增"""
        assert manager._increment_version("1.0") == "1.1"
        assert manager._increment_version("2.3") == "2.4"
        assert manager._increment_version("1.0.0") == "1.0.1"


class TestStatistics:
    """测试统计信息"""

    def test_basic_statistics(self, manager):
        """测试基本统计"""
        cot = ChainOfThought(
            name="test_cot",
            description="Test CoT",
            version="2.0",
            phases=[
                CoTPhase(
                    "phase1",
                    "First",
                    constraints=[
                        Constraint("c1", ConstraintType.HARD),
                        Constraint("c2", ConstraintType.SOFT),
                    ],
                    order=0,
                ),
            ],
            execution_count=10,
            success_rate=0.8,
        )
        manager.set_current_cot(cot)

        stats = manager.get_cot_statistics()

        assert stats["name"] == "test_cot"
        assert stats["version"] == "2.0"
        assert stats["phases_count"] == 1
        assert stats["total_constraints"] == 2
        assert stats["hard_constraints"] == 1
        assert stats["execution_count"] == 10
        assert stats["success_rate"] == 0.8

    def test_statistics_no_cot(self, manager):
        """测试无思维链时的统计"""
        stats = manager.get_cot_statistics()

        assert "error" in stats


class TestAnalyzeCoTTool:
    """测试分析工具"""

    @pytest.mark.asyncio
    async def test_analyze_tool(self, manager):
        """测试分析工具执行"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[CoTPhase("phase1", "First", order=0)],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test")
        manager.complete_execution(True, "Done")

        tool = AnalyzeCoTTool()
        result = await tool.execute(
            analysis_type="deep",
            cot_manager=manager,
        )

        assert "Analysis" in result
        assert "test" in result


class TestImproveCoTTool:
    """测试改进工具"""

    @pytest.mark.asyncio
    async def test_improve_tool(self, manager):
        """测试改进工具执行"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase(
                    "plan",
                    "Plan",
                    constraints=[Constraint("c1", ConstraintType.HARD)],
                    order=0,
                ),
            ],
        )
        manager.set_current_cot(cot)

        tool = ImproveCoTTool()
        result = await tool.execute(
            adjust_constraints=[
                {
                    "phase": "plan",
                    "constraint_index": 0,
                    "new_type": "soft",
                }
            ],
            save_new_version=False,
            cot_manager=manager,
        )

        assert "Improved" in result


class TestReflectCoTTool:
    """测试反思工具"""

    @pytest.mark.asyncio
    async def test_reflect_tool(self, manager):
        """测试反思工具执行"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[CoTPhase("phase1", "First", order=0)],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test")

        tool = ReflectCoTTool()
        result = await tool.execute(
            reflection="This went well",
            what_worked="Phase 1 was effective",
            what_didnt_work="Could use more validation",
            cot_manager=manager,
        )

        assert "Reflection Recorded" in result


class TestStatsCoTTool:
    """测试统计工具"""

    @pytest.mark.asyncio
    async def test_stats_tool(self, manager):
        """测试统计工具执行"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[CoTPhase("phase1", "First", order=0)],
            execution_count=5,
            success_rate=0.9,
        )
        manager.set_current_cot(cot)

        tool = StatsCoTTool()
        result = await tool.execute(cot_manager=manager)

        assert "Statistics" in result
        assert "5" in result  # execution count
        assert "90" in result  # success rate


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
