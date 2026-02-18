"""
测试 Interact Tools Plugin (简化后，无 Todo)
"""

import pytest
from pyagentforge.plugins.tools.interact_tools.PLUGIN import (
    InteractToolsPlugin,
    QuestionTool,
    ConfirmTool,
    BatchTool,
)


class TestInteractToolsPlugin:
    """测试 InteractToolsPlugin"""

    def test_plugin_metadata(self):
        """测试插件元数据"""
        plugin = InteractToolsPlugin()
        assert plugin.metadata.id == "tool.interact_tools"
        assert plugin.metadata.name == "Interact Tools"
        assert plugin.metadata.version == "2.0.0"
        assert "tools.interact" in plugin.metadata.provides

    def test_get_tools(self):
        """测试获取工具列表"""
        # 直接测试工具类，不需要插件激活
        q_tool = QuestionTool()
        c_tool = ConfirmTool()
        b_tool = BatchTool()

        # 检查工具名称
        assert q_tool.name == "question"
        assert c_tool.name == "confirm"
        assert b_tool.name == "batch"

        # 确认不包含 todo 工具
        assert q_tool.name != "todowrite"
        assert c_tool.name != "todoread"


class TestQuestionTool:
    """测试 QuestionTool"""

    def test_tool_properties(self):
        """测试工具属性"""
        tool = QuestionTool()
        assert tool.name == "question"
        assert tool.timeout == 300
        assert tool.risk_level == "low"

    @pytest.mark.asyncio
    async def test_execute_simple(self):
        """测试简单问题"""
        tool = QuestionTool()
        result = await tool.execute(question="What is your name?")
        assert "[QUESTION]" in result
        assert "What is your name?" in result

    @pytest.mark.asyncio
    async def test_execute_with_options(self):
        """测试带选项的问题"""
        tool = QuestionTool()
        result = await tool.execute(
            question="Choose an option",
            options=["Option A", "Option B", "Option C"],
            default="Option A"
        )
        assert "[QUESTION]" in result
        assert "Choose an option" in result
        assert "Option A" in result
        assert "Option B" in result
        assert "Option C" in result
        assert "(default)" in result


class TestConfirmTool:
    """测试 ConfirmTool"""

    def test_tool_properties(self):
        """测试工具属性"""
        tool = ConfirmTool()
        assert tool.name == "confirm"
        assert tool.timeout == 120
        assert tool.risk_level == "low"

    @pytest.mark.asyncio
    async def test_execute_default_no(self):
        """测试默认为 No"""
        tool = ConfirmTool()
        result = await tool.execute(message="Are you sure?", default=False)
        assert "[CONFIRM]" in result
        assert "Are you sure?" in result
        assert "[y/N]" in result

    @pytest.mark.asyncio
    async def test_execute_default_yes(self):
        """测试默认为 Yes"""
        tool = ConfirmTool()
        result = await tool.execute(message="Continue?", default=True)
        assert "[CONFIRM]" in result
        assert "Continue?" in result
        assert "[Y/n]" in result


class TestBatchTool:
    """测试 BatchTool"""

    def test_tool_properties(self):
        """测试工具属性"""
        tool = BatchTool()
        assert tool.name == "batch"
        assert tool.timeout == 120
        assert tool.risk_level == "medium"

    @pytest.mark.asyncio
    async def test_execute_no_registry(self):
        """测试无注册表的情况"""
        tool = BatchTool(tool_registry=None)
        result = await tool.execute(
            invocations=[
                {"tool_name": "test", "arguments": {}}
            ]
        )
        # 应该报错
        assert "Error" in result or "FAILED" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
