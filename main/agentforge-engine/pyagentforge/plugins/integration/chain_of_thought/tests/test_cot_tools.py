"""
思维链工具测试
"""

import tempfile
from pathlib import Path

import pytest

from pyagentforge.plugins.integration.chain_of_thought.cot_manager import ChainOfThoughtManager
from pyagentforge.plugins.integration.chain_of_thought.cot_tools import (
    CreateCoTTool,
    GetCoTInfoTool,
    LoadCoTTool,
    UpdateCoTTool,
    ValidatePlanTool,
)
from pyagentforge.plugins.integration.chain_of_thought.models import (
    ChainOfThought,
    Constraint,
    ConstraintType,
    CoTPhase,
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


class TestLoadCoTTool:
    """测试加载思维链工具"""

    @pytest.mark.asyncio
    async def test_load_existing_template(self, manager):
        """测试加载现有模板"""
        # 添加测试模板
        template = ChainOfThought(
            name="debugging",
            description="Debugging template",
            phases=[CoTPhase("test", "test", order=0)],
        )
        manager._templates["debugging"] = template

        tool = LoadCoTTool()
        result = await tool.execute(
            task_type="debugging",
            cot_manager=manager,
        )

        assert "Loaded Chain of Thought" in result
        assert "debugging" in result

    @pytest.mark.asyncio
    async def test_load_nonexistent_template(self, manager):
        """测试加载不存在的模板"""
        tool = LoadCoTTool()
        result = await tool.execute(
            task_type="nonexistent",
            cot_manager=manager,
        )

        assert "Error" in result
        assert "No CoT found" in result


class TestUpdateCoTTool:
    """测试更新思维链工具"""

    @pytest.mark.asyncio
    async def test_update_existing_phase(self, manager):
        """测试更新现有阶段"""
        # 设置当前思维链
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase("plan", "Plan phase", order=0),
            ],
        )
        manager.set_current_cot(cot)

        tool = UpdateCoTTool()
        result = await tool.execute(
            phase="plan",
            lessons_learned="Always verify inputs",
            cot_manager=manager,
        )

        assert "Updated" in result
        assert "Always verify inputs" in cot.get_phase("plan").prompt

    @pytest.mark.asyncio
    async def test_update_nonexistent_phase(self, manager):
        """测试更新不存在的阶段"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[CoTPhase("phase1", "prompt", order=0)],
        )
        manager.set_current_cot(cot)

        tool = UpdateCoTTool()
        result = await tool.execute(
            phase="nonexistent",
            lessons_learned="test",
            cot_manager=manager,
        )

        assert "Error" in result
        assert "not found" in result


class TestValidatePlanTool:
    """测试验证计划工具"""

    @pytest.mark.asyncio
    async def test_validate_plan_no_cot(self, manager):
        """测试无思维链时验证"""
        tool = ValidatePlanTool()
        result = await tool.execute(
            plan_steps=[{"description": "step1"}],
            cot_manager=manager,
        )

        assert "No chain of thought loaded" in result

    @pytest.mark.asyncio
    async def test_validate_plan_with_cot(self, manager):
        """测试有思维链时验证"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[
                CoTPhase(
                    "plan",
                    "planning",
                    constraints=[
                        Constraint("必须有验证", ConstraintType.SOFT),
                    ],
                    order=0,
                ),
            ],
        )
        manager.set_current_cot(cot)
        manager.start_execution("test_session")

        tool = ValidatePlanTool()
        result = await tool.execute(
            plan_steps=[{"description": "step1"}],
            fail_on_violation=False,
            cot_manager=manager,
        )

        assert "Validation Result" in result


class TestGetCoTInfoTool:
    """测试获取信息工具"""

    @pytest.mark.asyncio
    async def test_get_current_cot(self, manager):
        """测试获取当前思维链"""
        cot = ChainOfThought(
            name="test",
            description="test description",
            phases=[CoTPhase("phase1", "prompt", order=0)],
        )
        manager.set_current_cot(cot)

        tool = GetCoTInfoTool()
        result = await tool.execute(
            action="current",
            cot_manager=manager,
        )

        assert "test" in result
        assert "phase1" in result

    @pytest.mark.asyncio
    async def test_list_templates(self, manager):
        """测试列出模板"""
        template = ChainOfThought(
            name="template1",
            description="Template 1",
            phases=[],
        )
        manager._templates["template1"] = template

        tool = GetCoTInfoTool()
        result = await tool.execute(
            action="list",
            cot_manager=manager,
        )

        assert "template1" in result


class TestCreateCoTTool:
    """测试创建思维链工具"""

    @pytest.mark.asyncio
    async def test_create_new_cot(self, manager):
        """测试创建新思维链"""
        tool = CreateCoTTool()
        result = await tool.execute(
            name="custom_cot",
            description="Custom CoT",
            phases=[
                {
                    "name": "phase1",
                    "prompt": "First phase",
                    "order": 0,
                    "constraints": [
                        {"description": "must validate", "type": "hard"}
                    ],
                },
            ],
            tags=["custom", "test"],
            cot_manager=manager,
        )

        assert "Created" in result
        assert "custom_cot" in result

        # 验证已保存
        loaded = manager.get_agent_cot("custom_cot")
        assert loaded is not None
        assert loaded.name == "custom_cot"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
