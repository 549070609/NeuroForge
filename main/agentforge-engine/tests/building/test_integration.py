"""
Integration Tests for Agent Building Layer

测试完整的构建-加载-运行流程
"""

import asyncio
import pytest
import tempfile
from pathlib import Path

from pyagentforge.agents.metadata import AgentCategory, AgentCost
from pyagentforge.agents.registry import get_agent_registry
from pyagentforge.building import (
    AgentBuilder,
    AgentFactory,
    AgentLoader,
    AgentSchema,
    AgentTemplate,
)
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.building.schema import AgentIdentity
from unittest.mock import Mock


def create_test_factory() -> AgentFactory:
    """创建测试 Factory"""
    tool_registry = ToolRegistry()
    provider_factory = lambda name: Mock(name=name)

    registry = get_agent_registry()

    return AgentFactory(
        provider_factory=provider_factory,
        tool_registry=tool_registry,
        agent_registry=registry,
    )


class TestFullWorkflow:
    """测试完整工作流"""

    @pytest.mark.asyncio
    async def test_builder_to_registry_to_engine(self):
        """测试：Builder → Registry → Engine"""
        # 1. 使用 Builder 创建 Schema
        schema = (
            AgentBuilder()
            .with_name("integration-test")
            .with_description("Integration test agent")
            .with_category(AgentCategory.CODING)
            .with_model("claude-sonnet-4-20250514")
            .with_prompt("You are a test assistant.")
            .add_tools(["read"])
            .readonly(True)
            .build()
        )

        # 2. 注册到 Registry
        registry = get_agent_registry()
        registry.register_schema(schema)

        # 验证注册成功
        metadata = registry.get("integration-test")
        assert metadata is not None
        assert metadata.name == "integration-test"

        # 3. 使用 Factory 创建实例
        factory = create_test_factory()
        engine = factory.create_from_schema(schema)

        # 验证实例创建成功
        assert engine is not None
        assert engine.config.name == "integration-test"
        assert engine.config.readonly

    @pytest.mark.asyncio
    async def test_yaml_load_and_run(self):
        """测试：从 YAML 加载并创建实例"""
        yaml_content = """
identity:
  name: yaml-integration
  version: "1.0.0"
  description: "YAML integration test"

category: exploration
cost: free

model:
  model: "claude-sonnet-4-20250514"
  temperature: 0.5

capabilities:
  tools:
    - read
    - grep

behavior:
  system_prompt: "You explore code."

limits:
  is_readonly: true
  max_concurrent: 3
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                # 1. 加载
                factory = create_test_factory()
                loader = AgentLoader(factory)
                loaded = loader.load_from_yaml(f.name)

                # 2. 验证加载
                assert loaded.schema.identity.name == "yaml-integration"
                assert loaded.schema.category == AgentCategory.EXPLORATION

                # 3. 创建实例
                engine = factory.create_from_schema(loaded.schema)

                assert engine is not None
                assert engine.config.name == "yaml-integration"
            finally:
                Path(f.name).unlink()

    @pytest.mark.asyncio
    async def test_template_customization_workflow(self):
        """测试：模板自定义工作流"""
        # 1. 从模板开始
        schema = (
            AgentTemplate.reviewer()
            .with_name("my-custom-reviewer")
            .with_description("Customized reviewer")
            .with_model("claude-opus-4")
            .max_concurrent(5)
            .build()
        )

        # 2. 验证
        assert schema.category == AgentCategory.REVIEW
        assert schema.cost == AgentCost.CHEAP
        assert schema.model.model == "claude-opus-4"
        assert schema.limits.max_concurrent == 5

        # 3. 创建实例
        factory = create_test_factory()
        engine = factory.create_from_schema(schema)

        assert engine.config.name == "my-custom-reviewer"

    @pytest.mark.asyncio
    async def test_singleton_workflow(self):
        """测试：单例工作流"""
        factory = create_test_factory()

        schema = AgentSchema(
            identity=AgentIdentity(name="singleton-test"),
            category=AgentCategory.CODING,
        )

        # 1. 创建单例
        instance1 = factory.get_or_create_singleton(schema)

        # 2. 再次获取
        instance2 = factory.get_or_create_singleton(schema)

        # 3. 验证是同一个实例
        assert instance1 is instance2

        # 4. 销毁单例
        factory.destroy_singleton("singleton-test")

        assert not factory.has_singleton("singleton-test")

    @pytest.mark.asyncio
    async def test_pool_workflow(self):
        """测试：池化工作流"""
        factory = create_test_factory()

        schema = AgentSchema(
            identity=AgentIdentity(name="pool-test"),
            category=AgentCategory.CODING,
        )

        # 1. 创建池
        pool = factory.create_pool(schema, size=3)

        assert pool.size == 3
        assert pool.get_available_count() == 3

        # 2. 获取实例
        instance1 = factory.get_from_pool("pool-test")
        instance2 = factory.get_from_pool("pool-test")

        assert instance1 is not None
        assert instance2 is not None
        assert instance1 is not instance2
        assert pool.get_available_count() == 1

        # 3. 返回实例
        factory.return_to_pool("pool-test", instance1)

        assert pool.get_available_count() == 2

        # 4. 销毁池
        factory.destroy_pool("pool-test")

        assert factory.get_pool("pool-test") is None

    @pytest.mark.asyncio
    async def test_prototype_workflow(self):
        """测试：原型工作流"""
        factory = create_test_factory()

        # 1. 注册原型
        base_schema = AgentSchema(
            identity=AgentIdentity(name="prototype-base"),
            category=AgentCategory.REVIEW,
        )

        factory.register_prototype(base_schema)

        # 2. 从原型创建实例（无覆盖）
        instance1 = factory.create_from_prototype("prototype-base")

        assert instance1.config.name == "prototype-base"

        # 3. 从原型创建实例（带覆盖）
        instance2 = factory.create_from_prototype(
            "prototype-base",
            overrides={
                "identity": {"name": "prototype-derived"},
            },
        )

        # 验证
        assert "prototype-base" in factory.list_prototypes()


class TestRegistryIntegration:
    """测试 Registry 集成"""

    def test_find_by_capability(self):
        """测试按能力查找"""
        registry = get_agent_registry()

        # 查找具有 "read" 工具的 Agent
        agents = registry.find_by_capability("read")

        assert len(agents) > 0

    def test_find_by_tags(self):
        """测试按标签查找"""
        registry = get_agent_registry()

        # 创建带标签的 Agent
        schema = (
            AgentBuilder()
            .with_name("tagged-integration")
            .with_tags(["python", "testing"])
            .build()
        )

        registry.register_schema(schema)

        # 查找
        agents = registry.find_by_tags(["python"])

        assert len(agents) > 0
        names = [a.name for a in agents]
        assert "tagged-integration" in names

    def test_find_best_for_task(self):
        """测试智能匹配"""
        registry = get_agent_registry()

        # 测试匹配
        agent = registry.find_best_for_task("I need to review some code changes")

        assert agent is not None
        assert agent.category == AgentCategory.REVIEW

        agent2 = registry.find_best_for_task("Help me implement a new feature")

        assert agent2 is not None
        # 应该匹配到 coding 类型的 agent


class TestBackwardCompatibility:
    """测试向后兼容性"""

    def test_existing_metadata_still_works(self):
        """测试现有 AgentMetadata 仍然可用"""
        from pyagentforge.agents.metadata import AgentMetadata

        metadata = AgentMetadata(
            name="compat-test",
            description="Compatibility test",
            category=AgentCategory.CODING,
        )

        registry = get_agent_registry()
        registry.register(metadata)

        # 验证
        assert registry.get("compat-test") is not None

    def test_schema_from_metadata(self):
        """测试从 Metadata 创建 Schema"""
        from pyagentforge.agents.metadata import AgentMetadata

        metadata = AgentMetadata(
            name="schema-from-meta",
            description="From metadata",
            category=AgentCategory.PLANNING,
            cost=AgentCost.CHEAP,
            tools=["read"],
        )

        schema = AgentSchema.from_metadata(metadata)

        assert schema.identity.name == "schema-from-meta"
        assert schema.category == AgentCategory.PLANNING

    def test_schema_to_metadata_roundtrip(self):
        """测试 Schema ↔ Metadata 往返转换"""
        schema = (
            AgentBuilder()
            .with_name("roundtrip-test")
            .with_description("Roundtrip test")
            .with_category(AgentCategory.REVIEW)
            .with_cost(AgentCost.CHEAP)
            .add_tools(["read", "grep"])
            .with_prompt("Test prompt")
            .build()
        )

        # Schema → Metadata
        metadata = schema.to_agent_metadata()

        # Metadata → Schema
        schema2 = AgentSchema.from_metadata(metadata)

        # 验证
        assert schema2.identity.name == schema.identity.name
        assert schema2.category == schema.category
        assert schema2.cost == schema.cost


class TestErrorHandling:
    """测试错误处理"""

    def test_create_non_existent_agent(self):
        """测试创建不存在的 Agent"""
        factory = create_test_factory()

        with pytest.raises(ValueError, match="not found"):
            factory.create_from_name("non-existent-agent-xyz")

    def test_pool_exhaustion(self):
        """测试池耗尽"""
        factory = create_test_factory()

        schema = AgentSchema(
            identity=AgentIdentity(name="exhaustion-test"),
            category=AgentCategory.CODING,
        )

        factory.create_pool(schema, size=1)

        # 获取唯一的实例
        instance1 = factory.get_from_pool("exhaustion-test")

        # 再次获取应该返回 None
        instance2 = factory.get_from_pool("exhaustion-test")

        assert instance2 is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
