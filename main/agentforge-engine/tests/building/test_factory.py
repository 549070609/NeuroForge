"""
AgentFactory Tests
"""

import pytest
from unittest.mock import Mock, MagicMock

from pyagentforge.agents.metadata import AgentCategory, AgentCost
from pyagentforge.agents.building.factory import AgentFactory, AgentPool, InstanceState
from pyagentforge.agents.building.schema import AgentSchema, AgentIdentity, ModelConfiguration
from pyagentforge.tools.registry import ToolRegistry


def create_test_schema() -> AgentSchema:
    """创建测试 Schema"""
    return AgentSchema(
        identity=AgentIdentity(name="test-factory-agent"),
        category=AgentCategory.CODING,
        cost=AgentCost.MODERATE,
        model=ModelConfiguration(model="claude-sonnet-4-20250514"),
    )


def create_mock_provider(provider_name: str):
    """创建 Mock Provider"""
    mock = Mock()
    mock.name = provider_name
    return mock


def create_test_factory() -> AgentFactory:
    """创建测试 Factory"""
    tool_registry = ToolRegistry()
    provider_factory = create_mock_provider

    return AgentFactory(
        provider_factory=provider_factory,
        tool_registry=tool_registry,
    )


class TestAgentFactory:
    """测试 AgentFactory"""

    def test_factory_create_from_schema(self):
        """测试从 Schema 创建"""
        factory = create_test_factory()
        schema = create_test_schema()

        engine = factory.create_from_schema(schema)

        assert engine is not None
        assert engine.config.name == "test-factory-agent"

    def test_factory_create_from_name(self):
        """测试从名称创建"""
        factory = create_test_factory()

        # 使用内置的 "explore" agent
        engine = factory.create_from_name("explore")

        assert engine is not None
        assert engine.config.name == "explore"

    def test_factory_create_from_name_not_found(self):
        """测试从不存在的名称创建"""
        factory = create_test_factory()

        with pytest.raises(ValueError, match="not found"):
            factory.create_from_name("non-existent-agent")


class TestSingletonManagement:
    """测试单例管理"""

    def test_get_or_create_singleton(self):
        """测试获取或创建单例"""
        factory = create_test_factory()
        schema = create_test_schema()

        instance1 = factory.get_or_create_singleton(schema)
        instance2 = factory.get_or_create_singleton(schema)

        # 应该是同一个实例
        assert instance1 is instance2

    def test_has_singleton(self):
        """测试检查单例"""
        factory = create_test_factory()
        schema = create_test_schema()

        assert not factory.has_singleton("test-factory-agent")

        factory.get_or_create_singleton(schema)

        assert factory.has_singleton("test-factory-agent")

    def test_destroy_singleton(self):
        """测试销毁单例"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.get_or_create_singleton(schema)
        assert factory.has_singleton("test-factory-agent")

        result = factory.destroy_singleton("test-factory-agent")

        assert result
        assert not factory.has_singleton("test-factory-agent")

    def test_destroy_non_existent_singleton(self):
        """测试销毁不存在的单例"""
        factory = create_test_factory()

        result = factory.destroy_singleton("non-existent")

        assert not result

    def test_list_singletons(self):
        """测试列出单例"""
        factory = create_test_factory()

        assert factory.list_singletons() == []

        schema1 = AgentSchema(identity=AgentIdentity(name="singleton1"))
        schema2 = AgentSchema(identity=AgentIdentity(name="singleton2"))

        factory.get_or_create_singleton(schema1)
        factory.get_or_create_singleton(schema2)

        singletons = factory.list_singletons()

        assert len(singletons) == 2
        assert "singleton1" in singletons
        assert "singleton2" in singletons


class TestPoolManagement:
    """测试池化管理"""

    def test_create_pool(self):
        """测试创建池"""
        factory = create_test_factory()
        schema = create_test_schema()

        pool = factory.create_pool(schema, size=3)

        assert pool is not None
        assert pool.size == 3
        assert len(pool.get_all()) == 3

    def test_get_pool(self):
        """测试获取池"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.create_pool(schema, size=2)
        pool = factory.get_pool("test-factory-agent")

        assert pool is not None
        assert pool.size == 2

    def test_get_from_pool(self):
        """测试从池获取"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.create_pool(schema, size=2)
        instance = factory.get_from_pool("test-factory-agent")

        assert instance is not None

    def test_return_to_pool(self):
        """测试返回池"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.create_pool(schema, size=2)
        instance = factory.get_from_pool("test-factory-agent")

        # 返回池
        factory.return_to_pool("test-factory-agent", instance)

        pool = factory.get_pool("test-factory-agent")
        assert pool.get_available_count() == 2

    def test_destroy_pool(self):
        """测试销毁池"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.create_pool(schema, size=2)
        assert factory.get_pool("test-factory-agent") is not None

        result = factory.destroy_pool("test-factory-agent")

        assert result
        assert factory.get_pool("test-factory-agent") is None

    def test_list_pools(self):
        """测试列出池"""
        factory = create_test_factory()

        assert factory.list_pools() == []

        schema1 = AgentSchema(identity=AgentIdentity(name="pool1"))
        schema2 = AgentSchema(identity=AgentIdentity(name="pool2"))

        factory.create_pool(schema1, size=1)
        factory.create_pool(schema2, size=1)

        pools = factory.list_pools()

        assert len(pools) == 2
        assert "pool1" in pools
        assert "pool2" in pools


class TestPrototypeManagement:
    """测试原型管理"""

    def test_register_prototype(self):
        """测试注册原型"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.register_prototype(schema)

        assert "test-factory-agent" in factory.list_prototypes()

    def test_create_from_prototype(self):
        """测试从原型创建"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.register_prototype(schema)

        instance = factory.create_from_prototype("test-factory-agent")

        assert instance is not None
        assert instance.config.name == "test-factory-agent"

    def test_create_from_prototype_with_overrides(self):
        """测试从原型创建（带覆盖）"""
        factory = create_test_factory()
        schema = create_test_schema()

        factory.register_prototype(schema)

        instance = factory.create_from_prototype(
            "test-factory-agent",
            overrides={
                "identity": {"description": "Overridden description"},
            },
        )

        assert instance is not None

    def test_create_from_non_existent_prototype(self):
        """测试从不存在的原型创建"""
        factory = create_test_factory()

        with pytest.raises(ValueError, match="not found"):
            factory.create_from_prototype("non-existent")

    def test_list_prototypes(self):
        """测试列出原型"""
        factory = create_test_factory()

        assert factory.list_prototypes() == []

        schema1 = AgentSchema(identity=AgentIdentity(name="proto1"))
        schema2 = AgentSchema(identity=AgentIdentity(name="proto2"))

        factory.register_prototype(schema1)
        factory.register_prototype(schema2)

        prototypes = factory.list_prototypes()

        assert len(prototypes) == 2
        assert "proto1" in prototypes
        assert "proto2" in prototypes


class TestAgentPool:
    """测试 AgentPool"""

    def test_pool_initialize(self):
        """测试池初始化"""
        factory = create_test_factory()
        schema = create_test_schema()

        pool = AgentPool(schema, factory, size=3)
        pool.initialize()

        assert len(pool.get_all()) == 3
        assert pool.get_available_count() == 3

    def test_pool_acquire_and_release(self):
        """测试池获取和释放"""
        factory = create_test_factory()
        schema = create_test_schema()

        pool = AgentPool(schema, factory, size=2)
        pool.initialize()

        # 获取一个
        instance1 = pool.acquire()
        assert instance1 is not None
        assert pool.get_available_count() == 1

        # 再获取一个
        instance2 = pool.acquire()
        assert instance2 is not None
        assert pool.get_available_count() == 0

        # 池已空
        instance3 = pool.acquire()
        assert instance3 is None

        # 释放
        pool.release(instance1)
        assert pool.get_available_count() == 1

    def test_pool_destroy(self):
        """测试池销毁"""
        factory = create_test_factory()
        schema = create_test_schema()

        pool = AgentPool(schema, factory, size=2)
        pool.initialize()

        pool.destroy()

        assert len(pool.get_all()) == 0


class TestFactoryStats:
    """测试工厂统计"""

    def test_get_stats(self):
        """测试获取统计"""
        factory = create_test_factory()

        stats = factory.get_stats()

        assert "singletons" in stats
        assert "pools" in stats
        assert "prototypes" in stats

    def test_get_stats_with_data(self):
        """测试带数据的统计"""
        factory = create_test_factory()

        # 添加单例
        schema1 = AgentSchema(identity=AgentIdentity(name="singleton1"))
        factory.get_or_create_singleton(schema1)

        # 添加池
        schema2 = AgentSchema(identity=AgentIdentity(name="pool1"))
        factory.create_pool(schema2, size=3)

        # 添加原型
        schema3 = AgentSchema(identity=AgentIdentity(name="prototype1"))
        factory.register_prototype(schema3)

        stats = factory.get_stats()

        assert len(stats["singletons"]) == 1
        assert len(stats["pools"]) == 1
        assert stats["pools"]["pool1"]["size"] == 3
        assert len(stats["prototypes"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
