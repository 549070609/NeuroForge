"""
思维链 Phase 4 高级特性测试

测试版本管理、组合、导入导出等高级功能。
"""

import json
import tempfile
from pathlib import Path

import pytest

from pyagentforge.plugins.integration.chain_of_thought.cot_manager import ChainOfThoughtManager
from pyagentforge.plugins.integration.chain_of_thought.cot_tools import (
    CloneCoTTool,
    CombineCoTTool,
    DeleteCoTTool,
    ExportCoTTool,
    ImportCoTTool,
    ListAllCoTTool,
    VersionCoTTool,
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


class TestVersionManagement:
    """测试版本管理"""

    def test_get_version_history(self, manager):
        """测试获取版本历史"""
        # 创建模板
        template = ChainOfThought(
            name="test",
            description="test",
            version="1.0",
            phases=[CoTPhase("phase1", "First", order=0)],
            execution_count=10,
            success_rate=0.9,
        )
        manager._templates["test"] = template

        # 创建 Agent 版本
        agent_cot = ChainOfThought(
            name="test",
            description="test agent",
            version="1.1",
            phases=[CoTPhase("phase1", "First", order=0)],
            source="agent",
            execution_count=5,
            success_rate=0.8,
        )
        manager.save_agent_cot(agent_cot)

        history = manager.get_version_history("test")

        assert len(history) == 2
        # 应该按版本排序
        assert history[0]["version"] == "1.1"

    def test_rollback_to_version(self, manager):
        """测试回滚版本"""
        # 创建多个版本
        v1 = ChainOfThought(
            name="test",
            description="v1",
            version="1.0",
            phases=[CoTPhase("phase1", "First", order=0)],
        )
        manager._templates["test"] = v1

        v2 = ChainOfThought(
            name="test",
            description="v2",
            version="2.0",
            phases=[CoTPhase("phase1", "Updated", order=0)],
            source="agent",
        )
        manager.save_agent_cot(v2)

        # 回滚到 v1
        rolled_back = manager.rollback_to_version("test", "1.0")

        assert rolled_back is not None
        assert rolled_back.version == "1.0"

    def test_parse_version(self, manager):
        """测试版本号解析"""
        assert manager._parse_version("1.0") == (1, 0)
        assert manager._parse_version("2.3.1") == (2, 3, 1)
        assert manager._parse_version("invalid") == (0,)


class TestChainCombination:
    """测试思维链组合"""

    def test_combine_sequential(self, manager):
        """测试顺序组合"""
        cot1 = ChainOfThought(
            name="cot1",
            description="First",
            phases=[
                CoTPhase("phase1", "Phase 1", order=0),
            ],
        )
        cot2 = ChainOfThought(
            name="cot2",
            description="Second",
            phases=[
                CoTPhase("phase2", "Phase 2", order=0),
            ],
        )

        manager._templates["cot1"] = cot1
        manager._templates["cot2"] = cot2

        combined = manager.combine_chains(
            chain_names=["cot1", "cot2"],
            combination_strategy="sequential",
        )

        assert combined is not None
        assert len(combined.phases) == 2
        assert combined.phases[0].order == 0
        assert combined.phases[1].order == 1

    def test_combine_merge(self, manager):
        """测试合并组合"""
        cot1 = ChainOfThought(
            name="cot1",
            description="First",
            phases=[
                CoTPhase(
                    "plan",
                    "Plan",
                    constraints=[Constraint("c1", ConstraintType.HARD)],
                    order=0,
                ),
            ],
        )
        cot2 = ChainOfThought(
            name="cot2",
            description="Second",
            phases=[
                CoTPhase(
                    "plan",
                    "Plan",
                    constraints=[Constraint("c2", ConstraintType.SOFT)],
                    order=0,
                ),
            ],
        )

        manager._templates["cot1"] = cot1
        manager._templates["cot2"] = cot2

        combined = manager.combine_chains(
            chain_names=["cot1", "cot2"],
            combination_strategy="merge",
        )

        assert combined is not None
        # 应该合并同名阶段，约束合并
        assert len(combined.phases) == 1
        assert len(combined.phases[0].constraints) == 2

    def test_combine_best_of(self, manager):
        """测试最佳组合"""
        cot1 = ChainOfThought(
            name="cot1",
            description="First",
            phases=[CoTPhase("phase1", "Phase 1", order=0)],
            execution_count=10,
            success_rate=0.9,
        )
        cot2 = ChainOfThought(
            name="cot2",
            description="Second",
            phases=[CoTPhase("phase2", "Phase 2", order=0)],
            execution_count=5,
            success_rate=0.8,
        )

        manager._templates["cot1"] = cot1
        manager._templates["cot2"] = cot2

        combined = manager.combine_chains(
            chain_names=["cot1", "cot2"],
            combination_strategy="best_of",
        )

        assert combined is not None


class TestImportExport:
    """测试导入导出"""

    def test_export_json(self, manager):
        """测试导出为 JSON"""
        cot = ChainOfThought(
            name="test",
            description="Test CoT",
            version="1.0",
            phases=[CoTPhase("phase1", "First", order=0)],
        )
        manager._templates["test"] = cot

        exported = manager.export_cot("test", "json")

        assert exported is not None
        # 应该是有效的 JSON
        parsed = json.loads(exported)
        assert parsed["name"] == "test"

    def test_export_markdown(self, manager):
        """测试导出为 Markdown"""
        cot = ChainOfThought(
            name="test",
            description="Test CoT",
            phases=[CoTPhase("phase1", "First", order=0)],
        )
        manager._templates["test"] = cot

        exported = manager.export_cot("test", "markdown")

        assert exported is not None
        assert "# test" in exported

    def test_import_json(self, manager):
        """测试从 JSON 导入"""
        data = json.dumps({
            "name": "imported",
            "description": "Imported CoT",
            "version": "1.0",
            "phases": [
                {
                    "name": "phase1",
                    "prompt": "First",
                    "constraints": [],
                    "order": 0,
                    "is_required": True,
                }
            ],
        })

        imported = manager.import_cot(data, "json")

        assert imported is not None
        assert imported.name == "imported"
        assert imported.source == "imported"

        # 检查已保存
        saved = manager.get_agent_cot("imported")
        assert saved is not None

    def test_import_overwrite(self, manager):
        """测试导入覆盖"""
        # 先创建一个
        existing = ChainOfThought(
            name="test",
            description="Existing",
            phases=[],
        )
        manager.save_agent_cot(existing)

        # 导入同名但不覆盖
        data = json.dumps({
            "name": "test",
            "description": "New",
            "version": "2.0",
            "phases": [],
        })

        imported = manager.import_cot(data, "json", overwrite=False)
        assert imported is None  # 不覆盖时应该失败

        # 覆盖导入
        imported = manager.import_cot(data, "json", overwrite=True)
        assert imported is not None


class TestManagement:
    """测试管理功能"""

    def test_list_all_cots(self, manager):
        """测试列出所有思维链"""
        # 添加模板
        template = ChainOfThought(
            name="template1",
            description="Template",
            phases=[],
        )
        manager._templates["template1"] = template

        # 添加 Agent CoT
        agent_cot = ChainOfThought(
            name="agent1",
            description="Agent",
            phases=[],
            source="agent",
        )
        manager.save_agent_cot(agent_cot)

        all_cots = manager.list_all_cots()

        assert "template1" in all_cots["templates"]
        assert "agent1" in all_cots["agent_cots"]

    def test_delete_cot(self, manager):
        """测试删除思维链"""
        cot = ChainOfThought(
            name="to_delete",
            description="Delete me",
            phases=[],
            source="agent",
        )
        manager.save_agent_cot(cot)

        # 删除
        deleted = manager.delete_cot("to_delete", "agent")
        assert deleted is True

        # 检查已删除
        retrieved = manager.get_agent_cot("to_delete")
        assert retrieved is None

    def test_clone_cot(self, manager):
        """测试克隆思维链"""
        original = ChainOfThought(
            name="original",
            description="Original",
            phases=[CoTPhase("phase1", "First", order=0)],
            execution_count=10,
            success_rate=0.9,
        )
        manager._templates["original"] = original

        # 克隆
        cloned = manager.clone_cot("original", "cloned")

        assert cloned is not None
        assert cloned.name == "cloned"
        assert cloned.source == "agent"
        assert cloned.execution_count == 0  # 应该重置
        assert cloned.success_rate == 0.0

        # 检查已保存
        saved = manager.get_agent_cot("cloned")
        assert saved is not None


class TestPhase4Tools:
    """测试 Phase 4 工具"""

    @pytest.mark.asyncio
    async def test_version_tool(self, manager):
        """测试版本工具"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[],
        )
        manager._templates["test"] = cot

        tool = VersionCoTTool()
        result = await tool.execute(
            action="history",
            cot_name="test",
            cot_manager=manager,
        )

        assert "Version History" in result

    @pytest.mark.asyncio
    async def test_combine_tool(self, manager):
        """测试组合工具"""
        cot1 = ChainOfThought(name="cot1", description="1", phases=[])
        cot2 = ChainOfThought(name="cot2", description="2", phases=[])
        manager._templates["cot1"] = cot1
        manager._templates["cot2"] = cot2

        tool = CombineCoTTool()
        result = await tool.execute(
            chain_names=["cot1", "cot2"],
            strategy="sequential",
            save_result=False,
            cot_manager=manager,
        )

        assert "Combined" in result

    @pytest.mark.asyncio
    async def test_export_tool(self, manager):
        """测试导出工具"""
        cot = ChainOfThought(
            name="test",
            description="test",
            phases=[CoTPhase("phase1", "First", order=0)],
        )
        manager._templates["test"] = cot

        tool = ExportCoTTool()
        result = await tool.execute(
            cot_name="test",
            format="json",
            cot_manager=manager,
        )

        assert "Exported" in result

    @pytest.mark.asyncio
    async def test_import_tool(self, manager):
        """测试导入工具"""
        data = json.dumps({
            "name": "imported",
            "description": "Imported",
            "phases": [],
        })

        tool = ImportCoTTool()
        result = await tool.execute(
            data=data,
            format="json",
            cot_manager=manager,
        )

        assert "Imported" in result

    @pytest.mark.asyncio
    async def test_list_all_tool(self, manager):
        """测试列出所有工具"""
        tool = ListAllCoTTool()
        result = await tool.execute(cot_manager=manager)

        assert "All Chains" in result

    @pytest.mark.asyncio
    async def test_delete_tool(self, manager):
        """测试删除工具"""
        cot = ChainOfThought(
            name="to_delete",
            description="Delete",
            phases=[],
            source="agent",
        )
        manager.save_agent_cot(cot)

        tool = DeleteCoTTool()
        result = await tool.execute(
            cot_name="to_delete",
            source="agent",
            confirm=True,
            cot_manager=manager,
        )

        assert "deleted" in result.lower()

    @pytest.mark.asyncio
    async def test_clone_tool(self, manager):
        """测试克隆工具"""
        cot = ChainOfThought(
            name="original",
            description="Original",
            phases=[],
        )
        manager._templates["original"] = cot

        tool = CloneCoTTool()
        result = await tool.execute(
            source_name="original",
            new_name="cloned",
            cot_manager=manager,
        )

        assert "Cloned" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
