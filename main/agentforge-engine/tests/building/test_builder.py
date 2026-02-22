"""
AgentBuilder Tests
"""

import pytest

from pyagentforge.agents.metadata import AgentCategory, AgentCost
from pyagentforge.building.builder import AgentBuilder, AgentTemplate
from pyagentforge.building.schema import AgentSchema


class TestAgentBuilder:
    """测试 AgentBuilder"""

    def test_builder_creates_valid_schema(self):
        """测试 Builder 创建有效 Schema"""
        schema = (
            AgentBuilder()
            .with_name("test-agent")
            .with_description("Test description")
            .with_model("claude-sonnet-4-20250514")
            .add_tools(["read", "write"])
            .readonly(True)
            .build()
        )

        assert schema.identity.name == "test-agent"
        assert "read" in schema.capabilities.tools
        assert schema.limits.is_readonly

    def test_builder_fluent_api(self):
        """测试流畅 API 链式调用"""
        builder = AgentBuilder()

        # 所有方法应该返回 self
        assert builder.with_name("test") is builder
        assert builder.with_version("1.0.0") is builder
        assert builder.with_model("test-model") is builder

    def test_builder_with_all_tools(self):
        """测试设置所有工具"""
        schema = AgentBuilder().with_name("test").with_all_tools().build()

        assert schema.capabilities.tools == ["*"]

    def test_builder_model_configuration(self):
        """测试模型配置"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .with_model("claude-opus-4")
            .with_provider("anthropic")
            .with_temperature(0.5)
            .with_max_tokens(8192)
            .with_reasoning_effort("high")
            .build()
        )

        assert schema.model.model == "claude-opus-4"
        assert schema.model.provider == "anthropic"
        assert schema.model.temperature == 0.5
        assert schema.model.max_tokens == 8192
        assert schema.model.reasoning_effort == "high"

    def test_builder_behavior_configuration(self):
        """测试行为配置"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .with_prompt("You are helpful.")
            .use_when(["help", "assistance"])
            .avoid_when(["ignore"])
            .with_key_trigger(r"\bhelp\b")
            .build()
        )

        assert schema.behavior.system_prompt == "You are helpful."
        assert "help" in schema.behavior.use_when
        assert "ignore" in schema.behavior.avoid_when
        assert schema.behavior.key_trigger == r"\bhelp\b"

    def test_builder_limits_configuration(self):
        """测试限制配置"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .readonly(True)
            .background(False)
            .max_concurrent(5)
            .with_timeout(600)
            .with_max_iterations(100)
            .build()
        )

        assert schema.limits.is_readonly
        assert not schema.limits.supports_background
        assert schema.limits.max_concurrent == 5
        assert schema.limits.timeout == 600
        assert schema.limits.max_iterations == 100

    def test_builder_memory_configuration(self):
        """测试记忆配置"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .with_memory(max_messages=50)
            .persistent_session(True)
            .build()
        )

        assert schema.memory.enabled
        assert schema.memory.max_messages == 50
        assert schema.memory.persistent_session

    def test_builder_without_memory(self):
        """测试禁用记忆"""
        schema = AgentBuilder().with_name("test").without_memory().build()

        assert not schema.memory.enabled

    def test_builder_category_and_cost(self):
        """测试分类和成本"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .with_category(AgentCategory.REVIEW)
            .with_cost(AgentCost.CHEAP)
            .build()
        )

        assert schema.category == AgentCategory.REVIEW
        assert schema.cost == AgentCost.CHEAP

    def test_builder_tags(self):
        """测试标签"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .with_tags(["python", "testing"])
            .add_tag("automation")
            .build()
        )

        assert len(schema.identity.tags) == 3
        assert "python" in schema.identity.tags
        assert "automation" in schema.identity.tags

    def test_builder_append_prompt(self):
        """测试追加提示词"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .with_prompt("Base prompt.")
            .append_prompt("Additional info.")
            .build()
        )

        # 应该合并提示词
        assert "Base prompt." in schema.behavior.system_prompt
        assert "Additional info." in schema.behavior.system_prompt

    def test_builder_deny_and_ask_tools(self):
        """测试拒绝和确认工具"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .allow_tools(["read", "write", "bash"])
            .deny_tools(["rm", "sudo"])
            .ask_for_tools(["git"])
            .build()
        )

        assert "rm" in schema.capabilities.denied_tools
        assert "git" in schema.capabilities.ask_tools

    def test_builder_dependencies(self):
        """测试依赖配置"""
        schema = (
            AgentBuilder()
            .with_name("test")
            .requires(["agent1", "agent2"])
            .optional_requires(["agent3"])
            .conflicts_with(["agent4"])
            .build()
        )

        assert "agent1" in schema.dependencies.requires
        assert "agent3" in schema.dependencies.optional_requires
        assert "agent4" in schema.dependencies.conflicts_with

    def test_builder_build_and_register(self):
        """测试构建并注册"""
        schema = AgentBuilder().with_name("unique-test-agent-123").build_and_register()

        assert schema.identity.name == "unique-test-agent-123"

        # 应该在注册表中
        from pyagentforge.agents.registry import get_agent_registry

        registry = get_agent_registry()
        assert registry.get("unique-test-agent-123") is not None


class TestAgentBuilderInheritance:
    """测试 Builder 继承"""

    def test_inherit_from_schema(self):
        """测试从 Schema 继承"""
        base_schema = (
            AgentBuilder()
            .with_name("base")
            .with_model("claude-opus-4")
            .readonly(True)
            .build()
        )

        derived_schema = (
            AgentBuilder()
            .with_name("derived")
            .inherit_from(base_schema)
            .with_description("Derived agent")
            .build()
        )

        assert derived_schema.identity.name == "derived"
        assert derived_schema.model.model == "claude-opus-4"
        assert derived_schema.limits.is_readonly
        assert derived_schema.identity.description == "Derived agent"


class TestAgentTemplate:
    """测试 Agent 模板"""

    def test_template_explorer(self):
        """测试探索模板"""
        schema = AgentTemplate.explorer().with_name("my-explorer").build()

        assert schema.category == AgentCategory.EXPLORATION
        assert schema.cost == AgentCost.FREE
        assert schema.limits.is_readonly
        assert "read" in schema.capabilities.tools
        assert schema.limits.max_concurrent == 5

    def test_template_planner(self):
        """测试规划模板"""
        schema = AgentTemplate.planner().with_name("my-planner").build()

        assert schema.category == AgentCategory.PLANNING
        assert schema.cost == AgentCost.CHEAP
        assert schema.limits.is_readonly
        assert not schema.limits.supports_background

    def test_template_coder(self):
        """测试编码模板"""
        schema = AgentTemplate.coder().with_name("my-coder").build()

        assert schema.category == AgentCategory.CODING
        assert schema.cost == AgentCost.EXPENSIVE
        assert not schema.limits.is_readonly
        assert schema.capabilities.tools == ["*"]

    def test_template_reviewer(self):
        """测试审查模板"""
        schema = AgentTemplate.reviewer().with_name("my-reviewer").build()

        assert schema.category == AgentCategory.REVIEW
        assert schema.cost == AgentCost.CHEAP
        assert schema.limits.is_readonly

    def test_template_researcher(self):
        """测试研究模板"""
        schema = AgentTemplate.researcher().with_name("my-researcher").build()

        assert schema.category == AgentCategory.RESEARCH
        assert schema.cost == AgentCost.FREE
        assert "webfetch" in schema.capabilities.tools

    def test_template_advisor(self):
        """测试顾问模板"""
        schema = AgentTemplate.advisor().with_name("my-advisor").build()

        assert schema.category == AgentCategory.REASONING
        assert schema.cost == AgentCost.EXPENSIVE
        assert schema.model.reasoning_effort == "xhigh"

    def test_template_customization(self):
        """测试模板自定义"""
        schema = (
            AgentTemplate.coder()
            .with_name("custom-coder")
            .with_model("claude-sonnet-4-20250514")
            .max_concurrent(5)
            .build()
        )

        assert schema.identity.name == "custom-coder"
        assert schema.model.model == "claude-sonnet-4-20250514"
        assert schema.limits.max_concurrent == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
