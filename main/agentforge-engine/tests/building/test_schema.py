"""
AgentSchema Tests
"""

import pytest

from pyagentforge.agents.metadata import AgentCategory, AgentCost, AgentMetadata
from pyagentforge.agents.building.schema import (
    AgentIdentity,
    AgentSchema,
    BehaviorDefinition,
    CapabilityDefinition,
    DependencyDefinition,
    ExecutionLimits,
    MemoryConfiguration,
    ModelConfiguration,
)


def create_test_schema() -> AgentSchema:
    """创建测试 Schema"""
    return AgentSchema(
        identity=AgentIdentity(
            name="test-agent",
            version="1.0.0",
            description="Test agent",
            tags=["test", "unit"],
        ),
        category=AgentCategory.CODING,
        cost=AgentCost.MODERATE,
        model=ModelConfiguration(
            model="claude-sonnet-4-20250514",
            temperature=0.8,
            max_tokens=2048,
        ),
        capabilities=CapabilityDefinition(
            tools=["read", "write", "bash"],
            denied_tools=["rm"],
        ),
        behavior=BehaviorDefinition(
            system_prompt="You are a test assistant.",
            use_when=["testing", "debugging"],
            avoid_when=["production"],
        ),
        limits=ExecutionLimits(
            is_readonly=False,
            max_concurrent=2,
        ),
    )


class TestAgentIdentity:
    """测试 AgentIdentity"""

    def test_create_identity(self):
        """测试创建身份"""
        identity = AgentIdentity(
            name="my-agent",
            version="2.0.0",
            description="My agent",
        )

        assert identity.name == "my-agent"
        assert identity.version == "2.0.0"
        assert identity.namespace == "default"
        assert identity.tags == []

    def test_identity_with_tags(self):
        """测试带标签的身份"""
        identity = AgentIdentity(
            name="tagged-agent",
            tags=["python", "testing", "automation"],
        )

        assert len(identity.tags) == 3
        assert "python" in identity.tags


class TestModelConfiguration:
    """测试 ModelConfiguration"""

    def test_default_model_config(self):
        """测试默认模型配置"""
        config = ModelConfiguration()

        assert config.provider == "anthropic"
        assert config.model == "default"
        assert config.temperature == 1.0
        assert config.max_tokens == 4096

    def test_custom_model_config(self):
        """测试自定义模型配置"""
        config = ModelConfiguration(
            provider="openai",
            model="gpt-4",
            temperature=0.5,
            max_tokens=8192,
            reasoning_effort="high",
        )

        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.5
        assert config.reasoning_effort == "high"


class TestCapabilityDefinition:
    """测试 CapabilityDefinition"""

    def test_default_capabilities(self):
        """测试默认能力"""
        caps = CapabilityDefinition()

        assert caps.tools == ["*"]
        assert caps.denied_tools == []
        assert caps.skills == []

    def test_custom_capabilities(self):
        """测试自定义能力"""
        caps = CapabilityDefinition(
            tools=["read", "write", "bash"],
            denied_tools=["rm", "sudo"],
            skills=["python", "testing"],
            commands=["!test", "!debug"],
        )

        assert len(caps.tools) == 3
        assert len(caps.denied_tools) == 2
        assert "python" in caps.skills


class TestBehaviorDefinition:
    """测试 BehaviorDefinition"""

    def test_behavior_with_prompt(self):
        """测试带提示词的行为"""
        behavior = BehaviorDefinition(
            system_prompt="You are helpful.",
            use_when=["help needed"],
        )

        assert behavior.system_prompt == "You are helpful."
        assert "help needed" in behavior.use_when


class TestAgentSchema:
    """测试 AgentSchema"""

    def test_create_schema(self):
        """测试创建 Schema"""
        schema = create_test_schema()

        assert schema.identity.name == "test-agent"
        assert schema.category == AgentCategory.CODING
        assert schema.cost == AgentCost.MODERATE
        assert len(schema.capabilities.tools) == 3

    def test_schema_to_metadata(self):
        """测试 Schema 转换为 AgentMetadata"""
        schema = create_test_schema()
        metadata = schema.to_agent_metadata()

        assert isinstance(metadata, AgentMetadata)
        assert metadata.name == "test-agent"
        assert metadata.category == AgentCategory.CODING
        assert metadata.tools == ["read", "write", "bash"]
        assert metadata.system_prompt == "You are a test assistant."

    def test_schema_to_config(self):
        """测试 Schema 转换为 AgentConfig"""
        schema = create_test_schema()
        config = schema.to_agent_config()

        assert config.name == "test-agent"
        assert config.model == "claude-sonnet-4-20250514"
        assert config.temperature == 0.8
        assert config.max_tokens == 2048
        assert config.allowed_tools == ["read", "write", "bash"]

    def test_schema_to_config_maps_max_iterations(self):
        """测试 max_iterations 被映射到运行时配置。"""
        schema = create_test_schema()
        schema.limits.max_iterations = 7

        config = schema.to_agent_config()

        assert config.max_iterations == 7

    def test_schema_from_metadata(self):
        """测试从 AgentMetadata 创建 Schema"""
        metadata = AgentMetadata(
            name="from-meta",
            description="From metadata",
            category=AgentCategory.REVIEW,
            cost=AgentCost.CHEAP,
            tools=["read"],
            system_prompt="Review agent",
        )

        schema = AgentSchema.from_metadata(metadata)

        assert schema.identity.name == "from-meta"
        assert schema.category == AgentCategory.REVIEW
        assert schema.cost == AgentCost.CHEAP
        assert schema.behavior.system_prompt == "Review agent"

    def test_schema_content_hash(self):
        """测试内容哈希"""
        schema1 = create_test_schema()
        schema2 = create_test_schema()

        # 相同内容应该有相同哈希
        assert schema1.compute_content_hash() == schema2.compute_content_hash()

    def test_schema_content_hash_different(self):
        """测试不同内容的哈希"""
        schema1 = create_test_schema()

        schema2 = AgentSchema(
            identity=AgentIdentity(name="different-agent"),
            category=AgentCategory.CODING,
        )

        # 不同内容应该有不同哈希
        assert schema1.compute_content_hash() != schema2.compute_content_hash()

    def test_schema_get_full_name(self):
        """测试完整名称"""
        schema1 = AgentSchema(
            identity=AgentIdentity(name="agent1"),
            category=AgentCategory.CODING,
        )
        assert schema1.get_full_name() == "agent1"

        schema2 = AgentSchema(
            identity=AgentIdentity(name="agent2", namespace="custom"),
            category=AgentCategory.CODING,
        )
        assert schema2.get_full_name() == "custom/agent2"

    def test_schema_equality(self):
        """测试相等比较"""
        schema1 = create_test_schema()
        schema2 = create_test_schema()

        assert schema1 == schema2

    def test_schema_hash(self):
        """测试哈希"""
        schema = create_test_schema()

        # 应该能够用作字典键
        d = {schema: "test"}
        assert d[schema] == "test"


class TestSchemaValidation:
    """测试 Schema 验证"""

    def test_invalid_temperature(self):
        """测试无效温度"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ModelConfiguration(temperature=3.0)

    def test_invalid_max_tokens(self):
        """测试无效 max_tokens"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ModelConfiguration(max_tokens=0)


class TestSchemaSerialization:
    """测试 Schema 序列化"""

    def test_schema_model_dump(self):
        """测试模型导出"""
        schema = create_test_schema()
        data = schema.model_dump()

        assert "identity" in data
        assert data["identity"]["name"] == "test-agent"
        assert data["category"] == AgentCategory.CODING

    def test_schema_model_dump_json(self):
        """测试 JSON 导出"""
        schema = create_test_schema()
        json_str = schema.model_dump_json()

        assert isinstance(json_str, str)
        assert "test-agent" in json_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
