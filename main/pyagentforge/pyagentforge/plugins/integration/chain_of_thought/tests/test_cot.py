"""
思维链系统测试
"""

import pytest
from pathlib import Path
import tempfile
import json

from pyagentforge.plugins.integration.chain_of_thought.models import (
    ChainOfThought,
    CoTPhase,
    Constraint,
    ConstraintType,
    ConstraintViolation,
    CoTExecutionTrace,
)
from pyagentforge.plugins.integration.chain_of_thought.cot_manager import ChainOfThoughtManager


class TestModels:
    """测试数据模型"""

    def test_constraint_creation(self):
        """测试约束创建"""
        constraint = Constraint(
            description="必须输出问题重述",
            constraint_type=ConstraintType.HARD,
        )

        assert constraint.description == "必须输出问题重述"
        assert constraint.constraint_type == ConstraintType.HARD

    def test_constraint_validation(self):
        """测试约束验证"""
        # 带自定义验证器的约束
        constraint = Constraint(
            description="值必须大于10",
            constraint_type=ConstraintType.HARD,
            validator=lambda x: x > 10,
        )

        is_valid, details = constraint.validate(15)
        assert is_valid is True
        assert details == ""

        is_valid, details = constraint.validate(5)
        assert is_valid is False
        assert details == "值必须大于10"

    def test_cot_phase_creation(self):
        """测试阶段创建"""
        phase = CoTPhase(
            name="understand",
            prompt="理解问题",
            constraints=[
                Constraint("必须输出", ConstraintType.HARD),
            ],
            order=0,
        )

        assert phase.name == "understand"
        assert len(phase.constraints) == 1

    def test_cot_phase_to_dict(self):
        """测试阶段序列化"""
        phase = CoTPhase(
            name="test",
            prompt="test prompt",
            constraints=[
                Constraint("constraint 1", ConstraintType.HARD),
            ],
            order=1,
        )

        data = phase.to_dict()
        assert data["name"] == "test"
        assert data["prompt"] == "test prompt"
        assert len(data["constraints"]) == 1
        assert data["constraints"][0]["type"] == "hard"

    def test_cot_phase_from_dict(self):
        """测试阶段反序列化"""
        data = {
            "name": "test",
            "prompt": "test prompt",
            "constraints": [
                {"description": "constraint 1", "type": "soft"}
            ],
            "order": 2,
            "is_required": False,
        }

        phase = CoTPhase.from_dict(data)
        assert phase.name == "test"
        assert phase.prompt == "test prompt"
        assert len(phase.constraints) == 1
        assert phase.constraints[0].constraint_type == ConstraintType.SOFT
        assert phase.is_required is False

    def test_chain_of_thought_creation(self):
        """测试思维链创建"""
        cot = ChainOfThought(
            name="test_cot",
            description="测试思维链",
            phases=[
                CoTPhase("phase1", "prompt1", order=0),
                CoTPhase("phase2", "prompt2", order=1),
            ],
        )

        assert cot.name == "test_cot"
        assert len(cot.phases) == 2

    def test_chain_of_thought_get_phase(self):
        """测试获取阶段"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase("understand", "理解", order=0),
                CoTPhase("analyze", "分析", order=1),
            ],
        )

        phase = cot.get_phase("analyze")
        assert phase is not None
        assert phase.name == "analyze"

        phase = cot.get_phase("nonexistent")
        assert phase is None

    def test_chain_of_thought_get_ordered_phases(self):
        """测试获取排序后的阶段"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase("phase3", "3", order=2),
                CoTPhase("phase1", "1", order=0),
                CoTPhase("phase2", "2", order=1),
            ],
        )

        ordered = cot.get_ordered_phases()
        assert len(ordered) == 3
        assert ordered[0].name == "phase1"
        assert ordered[1].name == "phase2"
        assert ordered[2].name == "phase3"

    def test_chain_of_thought_serialization(self):
        """测试思维链序列化"""
        cot = ChainOfThought(
            name="test",
            description="test description",
            phases=[
                CoTPhase(
                    "phase1",
                    "prompt1",
                    constraints=[Constraint("c1", ConstraintType.HARD)],
                    order=0,
                ),
            ],
            version="2.0",
            tags=["test", "unit"],
        )

        data = cot.to_dict()
        assert data["name"] == "test"
        assert data["version"] == "2.0"
        assert "test" in data["tags"]

        # 往返测试
        restored = ChainOfThought.from_dict(data)
        assert restored.name == cot.name
        assert restored.version == cot.version
        assert len(restored.phases) == len(cot.phases)

    def test_execution_trace(self):
        """测试执行轨迹"""
        trace = CoTExecutionTrace(
            cot_name="test_cot",
            session_id="session_123",
        )

        # 添加阶段结果
        trace.add_phase_result("understand", "problem understood")
        assert "understand" in trace.phase_results

        # 添加违反
        trace.add_violation(ConstraintViolation(
            phase_name="plan",
            constraint_description="missing validation",
            constraint_type=ConstraintType.SOFT,
            violation_details="no validation step",
        ))
        assert len(trace.violations) == 1

        # 完成
        trace.complete(success=True, reflection="good execution")
        assert trace.end_time is not None
        assert trace.success is True


class TestChainOfThoughtManager:
    """测试思维链管理器"""

    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir) / "templates"
            agent_dir = Path(tmpdir) / "agent_cot"
            templates_dir.mkdir()
            agent_dir.mkdir()
            yield templates_dir, agent_dir

    @pytest.fixture
    def manager(self, temp_dirs):
        """创建管理器实例"""
        templates_dir, agent_dir = temp_dirs
        return ChainOfThoughtManager(
            templates_dir=templates_dir,
            agent_cot_dir=agent_dir,
        )

    def test_manager_initialization(self, manager):
        """测试管理器初始化"""
        assert manager is not None
        assert manager.list_templates() == []

    def test_create_and_get_cot(self, manager):
        """测试创建和获取思维链"""
        cot = manager.create_cot_from_template(
            name="test_cot",
            description="test description",
            phases=[
                {
                    "name": "phase1",
                    "prompt": "prompt1",
                    "order": 0,
                    "constraints": [
                        {"description": "c1", "type": "hard"}
                    ],
                },
            ],
        )

        assert cot.name == "test_cot"
        assert len(cot.phases) == 1

        # 保存
        manager.save_agent_cot(cot)

        # 获取
        retrieved = manager.get_agent_cot("test_cot")
        assert retrieved is not None
        assert retrieved.name == "test_cot"

    def test_load_cot_priority(self, manager):
        """测试加载思维链优先级"""
        # 创建 Agent CoT
        agent_cot = ChainOfThought(
            name="debugging",
            description="Agent generated",
            phases=[CoTPhase("test", "test", order=0)],
            source="agent",
        )
        manager.save_agent_cot(agent_cot)

        # 创建模板
        template = ChainOfThought(
            name="debugging",
            description="Template",
            phases=[CoTPhase("test", "test", order=0)],
            source="user",
        )
        manager._templates["debugging"] = template

        # 优先 Agent
        loaded = manager.load_cot("debugging", prefer_agent=True)
        assert loaded.source == "agent"

        # 优先模板
        loaded = manager.load_cot("debugging", prefer_agent=False)
        assert loaded.source == "user"

    def test_execution_tracking(self, manager):
        """测试执行跟踪"""
        # 设置当前思维链
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[CoTPhase("phase1", "prompt", order=0)],
        )
        manager.set_current_cot(cot)

        # 开始执行
        trace = manager.start_execution("session_123")
        assert trace is not None
        assert trace.cot_name == "test"

        # 记录结果
        manager.record_phase_result("phase1", "result1")
        assert "phase1" in trace.phase_results

        # 完成
        manager.complete_execution(True, "success")
        assert trace.success is True
        assert trace.end_time is not None

    def test_validate_plan(self, manager):
        """测试计划验证"""
        # 创建带约束的思维链
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

        # 没有验证步骤的计划
        plan_without_validation = [
            {"description": "step 1"},
            {"description": "step 2"},
        ]

        is_valid, violations = manager.validate_plan_against_cot(plan_without_validation)

        # 应该有违反
        assert len(violations) > 0

    def test_generate_system_prompt_extension(self, manager):
        """测试生成系统提示扩展"""
        cot = ChainOfThought(
            name="test",
            description="Test CoT",
            phases=[
                CoTPhase("phase1", "First phase", order=0),
                CoTPhase("phase2", "Second phase", order=1),
            ],
        )
        manager.set_current_cot(cot)

        extension = manager.generate_system_prompt_extension()

        assert "test" in extension.lower()
        assert "phase1" in extension or "First phase" in extension
        assert "phase2" in extension or "Second phase" in extension


class TestTemplateLoading:
    """测试模板加载"""

    def test_load_templates_from_directory(self):
        """测试从目录加载模板"""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir) / "templates"
            templates_dir.mkdir()

            # 创建测试模板文件
            template_data = {
                "name": "test_template",
                "description": "A test template",
                "version": "1.0",
                "phases": [
                    {
                        "name": "phase1",
                        "prompt": "First phase",
                        "order": 0,
                        "constraints": [],
                    }
                ],
            }

            template_file = templates_dir / "test_template.json"
            with open(template_file, "w", encoding="utf-8") as f:
                json.dump(template_data, f)

            # 创建管理器
            manager = ChainOfThoughtManager(templates_dir=templates_dir)

            # 检查是否加载
            templates = manager.list_templates()
            assert "test_template" in templates

            # 获取模板
            loaded = manager.get_template("test_template")
            assert loaded is not None
            assert loaded.name == "test_template"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
