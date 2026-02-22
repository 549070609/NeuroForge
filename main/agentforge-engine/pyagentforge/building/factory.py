"""
Agent Factory

提供工厂模式创建 Agent 实例，支持单例、池化和原型管理
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from pyagentforge.agents.registry import AgentRegistry, get_agent_registry
from pyagentforge.building.schema import AgentSchema
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentEngine
from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class InstanceState(str, Enum):
    """实例状态"""

    IDLE = "idle"  # 空闲
    ACTIVE = "active"  # 活跃
    BUSY = "busy"  # 忙碌
    ERROR = "error"  # 错误
    DESTROYED = "destroyed"  # 已销毁


@dataclass
class PoolEntry:
    """池条目"""

    instance: AgentEngine
    state: InstanceState = InstanceState.IDLE
    created_at: str = ""
    last_used: str = ""


class AgentPool:
    """Agent 实例池"""

    def __init__(self, schema: AgentSchema, factory: "AgentFactory", size: int = 3):
        """
        初始化实例池

        Args:
            schema: Agent Schema
            factory: Agent Factory
            size: 池大小
        """
        self.schema = schema
        self.factory = factory
        self.size = size
        self._pool: list[PoolEntry] = []

    def initialize(self) -> None:
        """初始化池"""
        import datetime

        for _ in range(self.size):
            instance = self.factory.create_from_schema(self.schema)
            entry = PoolEntry(
                instance=instance,
                state=InstanceState.IDLE,
                created_at=datetime.datetime.now().isoformat(),
            )
            self._pool.append(entry)

        logger.info(
            f"Initialized pool for {self.schema.identity.name} with {self.size} instances"
        )

    def acquire(self) -> Optional[AgentEngine]:
        """
        获取一个空闲实例

        Returns:
            AgentEngine 实例或 None
        """
        import datetime

        for entry in self._pool:
            if entry.state == InstanceState.IDLE:
                entry.state = InstanceState.ACTIVE
                entry.last_used = datetime.datetime.now().isoformat()
                return entry.instance

        return None

    def release(self, instance: AgentEngine) -> None:
        """释放实例回池"""
        for entry in self._pool:
            if entry.instance == instance:
                entry.state = InstanceState.IDLE
                break

    def get_available_count(self) -> int:
        """获取空闲实例数量"""
        return sum(1 for e in self._pool if e.state == InstanceState.IDLE)

    def get_all(self) -> list[PoolEntry]:
        """获取所有池条目"""
        return self._pool.copy()

    def destroy(self) -> None:
        """销毁池中所有实例"""
        for entry in self._pool:
            if entry.state != InstanceState.DESTROYED:
                # 标记为销毁
                entry.state = InstanceState.DESTROYED
                # 可选：调用 destroy 方法
                # self.factory.destroy_agent(entry.instance)

        self._pool.clear()
        logger.info(f"Destroyed pool for {self.schema.identity.name}")


class AgentFactory:
    """
    Agent 工厂

    负责创建、管理 AgentEngine 实例
    """

    def __init__(
        self,
        provider_factory: Callable[[str], BaseProvider],
        tool_registry: ToolRegistry,
        agent_registry: AgentRegistry | None = None,
        plugin_manager: Any = None,
    ):
        """
        初始化工厂

        Args:
            provider_factory: Provider 工厂函数
            tool_registry: 工具注册表
            agent_registry: Agent 注册表（可选）
            plugin_manager: 插件管理器（可选）
        """
        self._provider_factory = provider_factory
        self._tool_registry = tool_registry
        self._agent_registry = agent_registry or get_agent_registry()
        self._plugin_manager = plugin_manager

        # 单例管理
        self._singletons: dict[str, AgentEngine] = {}

        # 池化管理
        self._pools: dict[str, AgentPool] = {}

        # 原型管理
        self._prototypes: dict[str, AgentSchema] = {}

    # ==================== 实例化 ====================

    def create_from_schema(
        self,
        schema: AgentSchema,
        session_id: str | None = None,
        context: ContextManager | None = None,
    ) -> AgentEngine:
        """
        从 Schema 创建 AgentEngine 实例

        Args:
            schema: Agent Schema
            session_id: 会话 ID（可选）
            context: 上下文管理器（可选）

        Returns:
            AgentEngine 实例
        """
        # 检查并发限制
        if not self._agent_registry.can_spawn(schema.identity.name):
            raise RuntimeError(
                f"Cannot spawn more instances of '{schema.identity.name}': "
                f"max concurrent limit reached"
            )

        # 创建 Provider
        provider = self._provider_factory(schema.model.provider)

        # 创建工具子集
        tool_subset = self._create_filtered_tool_registry(schema)

        # 创建配置
        config = schema.to_agent_config()

        # 创建上下文
        if context is None:
            context = ContextManager(
                session_id=session_id,
                max_messages=schema.memory.max_messages,
                enable_memory=schema.memory.enabled,
            )

        # 创建 Engine
        engine = AgentEngine(
            provider=provider,
            tool_registry=tool_subset,
            config=config,
            context=context,
        )

        logger.info(f"Created AgentEngine from schema: {schema.identity.name}")
        return engine

    def create_from_name(
        self,
        name: str,
        session_id: str | None = None,
    ) -> AgentEngine:
        """
        从名称创建 AgentEngine 实例

        Args:
            name: Agent 名称
            session_id: 会话 ID（可选）

        Returns:
            AgentEngine 实例
        """
        # 从注册表查找
        metadata = self._agent_registry.get(name)
        if metadata is None:
            raise ValueError(f"Agent '{name}' not found in registry")

        # 转换为 Schema
        schema = AgentSchema.from_metadata(metadata)

        return self.create_from_schema(schema, session_id)

    def _create_filtered_tool_registry(self, schema: AgentSchema) -> ToolRegistry:
        """
        根据权限创建过滤后的工具注册表

        Args:
            schema: Agent Schema

        Returns:
            过滤后的 ToolRegistry
        """
        from pyagentforge.tools.permission import PermissionConfig, PermissionChecker

        # 创建权限配置
        perm_config = PermissionConfig(
            allowed=schema.capabilities.tools,
            denied=schema.capabilities.denied_tools,
            ask=schema.capabilities.ask_tools,
            command_whitelist=schema.capabilities.command_whitelist,
            command_blacklist=schema.capabilities.command_blacklist,
            allowed_paths=schema.capabilities.allowed_paths,
            denied_paths=schema.capabilities.denied_paths,
            allowed_hosts=schema.capabilities.allowed_hosts,
            denied_hosts=schema.capabilities.denied_hosts,
        )

        # 创建权限检查器
        checker = PermissionChecker(perm_config)

        # 如果允许所有工具
        if "*" in schema.capabilities.tools:
            return self._tool_registry

        # 创建子集注册表
        subset = ToolRegistry()

        for tool_name in schema.capabilities.tools:
            tool = self._tool_registry.get(tool_name)
            if tool:
                subset.register(tool)

        # 设置权限检查器
        subset.set_permission_checker(checker)

        return subset

    # ==================== 单例管理 ====================

    def get_or_create_singleton(
        self, schema: AgentSchema | str, session_id: str | None = None
    ) -> AgentEngine:
        """
        获取或创建单例实例

        Args:
            schema: Agent Schema 或名称
            session_id: 会话 ID（可选）

        Returns:
            AgentEngine 实例
        """
        # 获取名称
        name = schema.identity.name if isinstance(schema, AgentSchema) else schema

        # 检查是否已存在
        if name in self._singletons:
            return self._singletons[name]

        # 创建新实例
        if isinstance(schema, str):
            instance = self.create_from_name(schema, session_id)
        else:
            instance = self.create_from_schema(schema, session_id)

        # 注册为单例
        self._singletons[name] = instance

        logger.info(f"Created singleton instance: {name}")
        return instance

    def has_singleton(self, name: str) -> bool:
        """
        检查是否存在单例

        Args:
            name: Agent 名称

        Returns:
            是否存在
        """
        return name in self._singletons

    def destroy_singleton(self, name: str) -> bool:
        """
        销毁单例

        Args:
            name: Agent 名称

        Returns:
            是否成功
        """
        if name not in self._singletons:
            return False

        instance = self._singletons.pop(name)
        # 可选：调用销毁方法
        # await self.destroy_agent(instance)

        logger.info(f"Destroyed singleton instance: {name}")
        return True

    def list_singletons(self) -> list[str]:
        """列出所有单例"""
        return list(self._singletons.keys())

    # ==================== 池化管理 ====================

    def create_pool(self, schema: AgentSchema | str, size: int = 3) -> AgentPool:
        """
        创建实例池

        Args:
            schema: Agent Schema 或名称
            size: 池大小

        Returns:
            AgentPool 实例
        """
        # 获取 Schema
        if isinstance(schema, str):
            metadata = self._agent_registry.get(schema)
            if metadata is None:
                raise ValueError(f"Agent '{schema}' not found in registry")
            schema = AgentSchema.from_metadata(metadata)

        name = schema.identity.name

        # 检查是否已存在
        if name in self._pools:
            logger.warning(f"Pool already exists for {name}, returning existing pool")
            return self._pools[name]

        # 创建池
        pool = AgentPool(schema, self, size)
        pool.initialize()

        self._pools[name] = pool

        logger.info(f"Created pool for {name} with size {size}")
        return pool

    def get_pool(self, name: str) -> Optional[AgentPool]:
        """
        获取实例池

        Args:
            name: Agent 名称

        Returns:
            AgentPool 或 None
        """
        return self._pools.get(name)

    def get_from_pool(self, name: str) -> Optional[AgentEngine]:
        """
        从池中获取实例

        Args:
            name: Agent 名称

        Returns:
            AgentEngine 实例或 None
        """
        pool = self._pools.get(name)
        if pool:
            return pool.acquire()
        return None

    def return_to_pool(self, name: str, instance: AgentEngine) -> None:
        """
        将实例返回到池

        Args:
            name: Agent 名称
            instance: AgentEngine 实例
        """
        pool = self._pools.get(name)
        if pool:
            pool.release(instance)

    def destroy_pool(self, name: str) -> bool:
        """
        销毁实例池

        Args:
            name: Agent 名称

        Returns:
            是否成功
        """
        pool = self._pools.pop(name, None)
        if pool:
            pool.destroy()
            logger.info(f"Destroyed pool for {name}")
            return True
        return False

    def list_pools(self) -> list[str]:
        """列出所有池"""
        return list(self._pools.keys())

    # ==================== 原型管理 ====================

    def register_prototype(self, schema: AgentSchema) -> None:
        """
        注册原型

        Args:
            schema: Agent Schema
        """
        name = schema.identity.name
        self._prototypes[name] = schema
        logger.info(f"Registered prototype: {name}")

    def create_from_prototype(
        self,
        name: str,
        overrides: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> AgentEngine:
        """
        从原型创建实例

        Args:
            name: 原型名称
            overrides: 覆盖配置（可选）
            session_id: 会话 ID（可选）

        Returns:
            AgentEngine 实例
        """
        if name not in self._prototypes:
            raise ValueError(f"Prototype '{name}' not found")

        schema = self._prototypes[name]

        # 应用覆盖
        if overrides:
            schema = self._apply_overrides(schema, overrides)

        return self.create_from_schema(schema, session_id)

    def _apply_overrides(
        self, schema: AgentSchema, overrides: dict[str, Any]
    ) -> AgentSchema:
        """
        应用覆盖配置

        Args:
            schema: 原始 Schema
            overrides: 覆盖配置

        Returns:
            新的 Schema
        """
        import copy

        # 深拷贝
        new_schema = copy.deepcopy(schema)

        # 应用覆盖
        if "model" in overrides:
            for key, value in overrides["model"].items():
                setattr(new_schema.model, key, value)

        if "behavior" in overrides:
            for key, value in overrides["behavior"].items():
                setattr(new_schema.behavior, key, value)

        if "limits" in overrides:
            for key, value in overrides["limits"].items():
                setattr(new_schema.limits, key, value)

        if "identity" in overrides:
            for key, value in overrides["identity"].items():
                setattr(new_schema.identity, key, value)

        return new_schema

    def list_prototypes(self) -> list[str]:
        """列出所有原型"""
        return list(self._prototypes.keys())

    # ==================== 生命周期管理 ====================

    async def initialize_agent(self, engine: AgentEngine) -> None:
        """
        初始化 Agent

        Args:
            engine: AgentEngine 实例
        """
        # 调用初始化钩子（如果有）
        # 这里可以扩展为调用插件系统的钩子
        logger.info(f"Initializing agent: {engine.config.name}")

    async def activate_agent(self, engine: AgentEngine) -> None:
        """
        激活 Agent

        Args:
            engine: AgentEngine 实例
        """
        # 调用激活钩子
        logger.info(f"Activating agent: {engine.config.name}")

    async def deactivate_agent(self, engine: AgentEngine) -> None:
        """
        停用 Agent

        Args:
            engine: AgentEngine 实例
        """
        # 调用停用钩子
        logger.info(f"Deactivating agent: {engine.config.name}")

    async def destroy_agent(self, engine: AgentEngine) -> None:
        """
        销毁 Agent

        Args:
            engine: AgentEngine 实例
        """
        # 清理资源
        logger.info(f"Destroying agent: {engine.config.name}")

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        pool_stats = {}
        for name, pool in self._pools.items():
            pool_stats[name] = {
                "size": pool.size,
                "available": pool.get_available_count(),
            }

        return {
            "singletons": list(self._singletons.keys()),
            "pools": pool_stats,
            "prototypes": list(self._prototypes.keys()),
        }
