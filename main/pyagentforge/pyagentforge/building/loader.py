"""
Agent Loader

提供 Agent 的热插拔加载能力，支持 YAML、JSON 和 Python 格式
"""

import importlib.util
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

import yaml

from pyagentforge.agents.registry import AgentRegistry, get_agent_registry
from pyagentforge.building.factory import AgentFactory
from pyagentforge.building.schema import AgentSchema
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class LoadState(str, Enum):
    """加载状态"""

    PENDING = "pending"  # 等待加载
    LOADING = "loading"  # 正在加载
    LOADED = "loaded"  # 已加载
    ACTIVATING = "activating"  # 正在激活
    ACTIVE = "active"  # 已激活
    DEACTIVATING = "deactivating"  # 正在停用
    INACTIVE = "inactive"  # 已停用
    UNLOADING = "unloading"  # 正在卸载
    UNLOADED = "unloaded"  # 已卸载
    ERROR = "error"  # 错误


class AgentLoadError(Exception):
    """Agent 加载错误"""

    def __init__(self, message: str, agent_name: str | None = None):
        super().__init__(message)
        self.agent_name = agent_name


@dataclass
class LoadedAgent:
    """已加载的 Agent"""

    schema: AgentSchema
    state: LoadState = LoadState.LOADED
    loaded_at: str = ""
    file_path: str = ""
    error: str | None = None

    def __post_init__(self):
        if not self.loaded_at:
            self.loaded_at = datetime.now().isoformat()


class AgentDependencyResolver:
    """Agent 依赖解析器"""

    def __init__(self, loader: "AgentLoader"):
        self.loader = loader

    def resolve_load_order(self, agent_names: List[str]) -> List[str]:
        """
        解析加载顺序（拓扑排序）

        Args:
            agent_names: Agent 名称列表

        Returns:
            按依赖顺序排列的列表

        Raises:
            AgentLoadError: 循环依赖或缺失依赖
        """
        # 构建依赖图
        graph: dict[str, set[str]] = defaultdict(set)
        in_degree: dict[str, int] = defaultdict(int)

        # 初始化所有节点
        all_agents = set(agent_names)
        for name in agent_names:
            in_degree[name] = 0

        # 构建边
        for name in agent_names:
            loaded = self.loader.get_loaded(name)
            if loaded is None:
                continue

            for dep_id in loaded.schema.dependencies.requires:
                if dep_id not in all_agents:
                    raise AgentLoadError(
                        f"Agent {name} requires {dep_id} which is not in the load list",
                        name,
                    )
                graph[dep_id].add(name)
                in_degree[name] += 1

        # 拓扑排序 (Kahn's algorithm)
        queue = [name for name in agent_names if in_degree[name] == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(agent_names):
            # 检测循环依赖
            remaining = [n for n in agent_names if n not in result]
            raise AgentLoadError(
                f"Circular dependency detected among: {remaining}", None
            )

        return result

    def check_conflicts(self, schema: AgentSchema) -> tuple[bool, List[str]]:
        """
        检查冲突

        Args:
            schema: Agent Schema

        Returns:
            (是否有冲突, 冲突的 Agent 列表)
        """
        conflicts = []

        for conflict_id in schema.dependencies.conflicts_with:
            if self.loader.get_loaded(conflict_id) is not None:
                conflicts.append(conflict_id)

        return len(conflicts) > 0, conflicts


class AgentLoader:
    """
    Agent 加载器

    支持 YAML、JSON 和 Python 格式的 Agent 定义
    """

    def __init__(
        self,
        factory: AgentFactory,
        registry: AgentRegistry | None = None,
    ):
        """
        初始化加载器

        Args:
            factory: Agent Factory
            registry: Agent Registry（可选）
        """
        self._factory = factory
        self._registry = registry or get_agent_registry()

        # 已加载的 Agent
        self._loaded: dict[str, LoadedAgent] = {}

        # 依赖解析器
        self._dependency_resolver = AgentDependencyResolver(self)

        # 热重载监视器
        self._watcher: Any = None

    # ==================== 加载方法 ====================

    def load_from_yaml(self, path: str) -> LoadedAgent:
        """
        从 YAML 文件加载

        Args:
            path: 文件路径

        Returns:
            LoadedAgent 实例

        Raises:
            AgentLoadError: 加载失败
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                raise AgentLoadError(f"File not found: {path}")

            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            schema = self._parse_schema(data)
            return self._register_loaded(schema, str(file_path))

        except Exception as e:
            logger.error(f"Failed to load YAML from {path}: {e}")
            raise AgentLoadError(str(e))

    def load_from_json(self, path: str) -> LoadedAgent:
        """
        从 JSON 文件加载

        Args:
            path: 文件路径

        Returns:
            LoadedAgent 实例

        Raises:
            AgentLoadError: 加载失败
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                raise AgentLoadError(f"File not found: {path}")

            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            schema = self._parse_schema(data)
            return self._register_loaded(schema, str(file_path))

        except Exception as e:
            logger.error(f"Failed to load JSON from {path}: {e}")
            raise AgentLoadError(str(e))

    def load_from_python(self, path: str) -> LoadedAgent:
        """
        从 Python 文件加载

        Args:
            path: 文件路径

        Returns:
            LoadedAgent 实例

        Raises:
            AgentLoadError: 加载失败
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                raise AgentLoadError(f"File not found: {path}")

            # 动态加载模块
            spec = importlib.util.spec_from_file_location(
                f"agent_{file_path.stem}", file_path
            )
            if spec is None or spec.loader is None:
                raise AgentLoadError(f"Failed to load module from {path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找 Schema
            schema = None

            # 方式 1: 查找 AGENT_SCHEMA 变量
            if hasattr(module, "AGENT_SCHEMA"):
                schema = module.AGENT_SCHEMA

            # 方式 2: 调用 create_schema() 函数
            elif hasattr(module, "create_schema"):
                schema = module.create_schema()

            if schema is None:
                raise AgentLoadError(
                    f"No AGENT_SCHEMA or create_schema() found in {path}"
                )

            if not isinstance(schema, AgentSchema):
                raise AgentLoadError(f"AGENT_SCHEMA is not an AgentSchema instance")

            return self._register_loaded(schema, str(file_path))

        except Exception as e:
            logger.error(f"Failed to load Python from {path}: {e}")
            raise AgentLoadError(str(e))

    def load(self, path: str) -> LoadedAgent:
        """
        自动检测格式并加载

        Args:
            path: 文件路径

        Returns:
            LoadedAgent 实例

        Raises:
            AgentLoadError: 加载失败
        """
        file_path = Path(path)
        suffix = file_path.suffix.lower()

        if suffix in [".yaml", ".yml"]:
            return self.load_from_yaml(path)
        elif suffix == ".json":
            return self.load_from_json(path)
        elif suffix == ".py":
            return self.load_from_python(path)
        else:
            raise AgentLoadError(f"Unsupported file format: {suffix}")

    def load_directory(
        self,
        directory: str,
        recursive: bool = False,
    ) -> List[LoadedAgent]:
        """
        加载目录中的所有 Agent

        Args:
            directory: 目录路径
            recursive: 是否递归加载

        Returns:
            LoadedAgent 列表
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise AgentLoadError(f"Directory not found: {directory}")

        # 查找所有 Agent 文件
        patterns = ["*.yaml", "*.yml", "*.json", "*.py"]
        files = []

        for pattern in patterns:
            if recursive:
                files.extend(dir_path.rglob(pattern))
            else:
                files.extend(dir_path.glob(pattern))

        # 排除 __init__.py
        files = [f for f in files if f.name != "__init__.py"]

        # 加载所有文件
        loaded = []
        for file_path in files:
            try:
                agent = self.load(str(file_path))
                loaded.append(agent)
            except AgentLoadError as e:
                logger.warning(f"Failed to load {file_path}: {e}")

        # 解析依赖并按顺序加载
        if loaded:
            names = [a.schema.identity.name for a in loaded]
            ordered_names = self._dependency_resolver.resolve_load_order(names)

            # 重新排序
            name_to_agent = {a.schema.identity.name: a for a in loaded}
            loaded = [name_to_agent[name] for name in ordered_names]

        return loaded

    # ==================== 卸载方法 ====================

    def unload(self, name: str) -> bool:
        """
        卸载 Agent

        Args:
            name: Agent 名称

        Returns:
            是否成功
        """
        if name not in self._loaded:
            return False

        loaded = self._loaded[name]

        # 检查是否有其他 Agent 依赖它
        for other_name, other_loaded in self._loaded.items():
            if name in other_loaded.schema.dependencies.requires:
                logger.warning(
                    f"Cannot unload {name}: {other_name} depends on it"
                )
                return False

        # 从注册表移除
        self._registry.unregister(name)

        # 移除已加载记录
        del self._loaded[name]

        logger.info(f"Unloaded agent: {name}")
        return True

    def unload_all(self) -> int:
        """
        卸载所有 Agent

        Returns:
            卸载的数量
        """
        count = 0
        for name in list(self._loaded.keys()):
            if self.unload(name):
                count += 1
        return count

    # ==================== 热重载 ====================

    def reload(self, name: str) -> LoadedAgent:
        """
        重新加载 Agent

        Args:
            name: Agent 名称

        Returns:
            LoadedAgent 实例
        """
        loaded = self.get_loaded(name)
        if loaded is None:
            raise AgentLoadError(f"Agent '{name}' is not loaded")

        file_path = loaded.file_path
        if not file_path:
            raise AgentLoadError(f"Agent '{name}' has no file path")

        # 卸载
        self.unload(name)

        # 重新加载
        return self.load(file_path)

    def enable_hot_reload(self, watch_dir: str) -> None:
        """
        启用热重载

        Args:
            watch_dir: 监视的目录
        """
        try:
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent
            from watchdog.observers import Observer

            class AgentFileHandler(FileSystemEventHandler):
                def __init__(self, loader: AgentLoader):
                    self.loader = loader

                def on_modified(self, event: FileModifiedEvent):
                    if event.is_directory:
                        return

                    file_path = event.src_path
                    suffix = Path(file_path).suffix.lower()

                    if suffix in [".yaml", ".yml", ".json", ".py"]:
                        logger.info(f"File modified: {file_path}")

                        # 查找已加载的 Agent
                        for name, loaded in self.loader._loaded.items():
                            if loaded.file_path == file_path:
                                logger.info(f"Hot reloading agent: {name}")
                                try:
                                    self.loader.reload(name)
                                except Exception as e:
                                    logger.error(f"Hot reload failed: {e}")
                                break

            # 创建观察者
            observer = Observer()
            handler = AgentFileHandler(self)
            observer.schedule(handler, watch_dir, recursive=True)
            observer.start()

            self._watcher = observer
            logger.info(f"Hot reload enabled for: {watch_dir}")

        except ImportError:
            logger.warning(
                "watchdog not installed, hot reload disabled. "
                "Install with: pip install watchdog"
            )

    def disable_hot_reload(self) -> None:
        """禁用热重载"""
        if self._watcher:
            self._watcher.stop()
            self._watcher.join()
            self._watcher = None
            logger.info("Hot reload disabled")

    # ==================== 依赖解析 ====================

    def resolve_dependencies(self, agent_names: List[str]) -> List[str]:
        """
        解析依赖并返回加载顺序

        Args:
            agent_names: Agent 名称列表

        Returns:
            按依赖顺序排列的列表
        """
        return self._dependency_resolver.resolve_load_order(agent_names)

    # ==================== 状态查询 ====================

    def get_loaded(self, name: str) -> LoadedAgent | None:
        """
        获取已加载的 Agent

        Args:
            name: Agent 名称

        Returns:
            LoadedAgent 或 None
        """
        return self._loaded.get(name)

    def list_loaded(self) -> List[str]:
        """列出所有已加载的 Agent"""
        return list(self._loaded.keys())

    def get_state(self, name: str) -> LoadState | None:
        """
        获取加载状态

        Args:
            name: Agent 名称

        Returns:
            LoadState 或 None
        """
        loaded = self._loaded.get(name)
        return loaded.state if loaded else None

    # ==================== 内部方法 ====================

    def _parse_schema(self, data: dict[str, Any]) -> AgentSchema:
        """
        解析 Schema 数据

        Args:
            data: 字典数据

        Returns:
            AgentSchema 实例
        """
        from pyagentforge.agents.metadata import AgentCategory, AgentCost
        from pyagentforge.building.schema import (
            AgentIdentity,
            BehaviorDefinition,
            CapabilityDefinition,
            DependencyDefinition,
            ExecutionLimits,
            MemoryConfiguration,
            ModelConfiguration,
        )

        # 解析身份
        identity_data = data.get("identity", {})
        identity = AgentIdentity(
            name=identity_data.get("name", "unnamed"),
            version=identity_data.get("version", "1.0.0"),
            namespace=identity_data.get("namespace", "default"),
            description=identity_data.get("description", ""),
            tags=identity_data.get("tags", []),
            author=identity_data.get("author", ""),
            license=identity_data.get("license", "MIT"),
        )

        # 解析模型配置
        model_data = data.get("model", {})
        model = ModelConfiguration(
            provider=model_data.get("provider", "anthropic"),
            model=model_data.get("model", "claude-sonnet-4-20250514"),
            temperature=model_data.get("temperature", 1.0),
            max_tokens=model_data.get("max_tokens", 4096),
            reasoning_effort=model_data.get("reasoning_effort", "medium"),
            timeout=model_data.get("timeout", 120),
        )

        # 解析能力
        capabilities_data = data.get("capabilities", {})
        capabilities = CapabilityDefinition(
            tools=capabilities_data.get("tools", ["*"]),
            denied_tools=capabilities_data.get("denied_tools", []),
            ask_tools=capabilities_data.get("ask_tools", []),
            skills=capabilities_data.get("skills", []),
            commands=capabilities_data.get("commands", []),
        )

        # 解析行为
        behavior_data = data.get("behavior", {})
        behavior = BehaviorDefinition(
            system_prompt=behavior_data.get("system_prompt", ""),
            prompt_append=behavior_data.get("prompt_append", ""),
            use_when=behavior_data.get("use_when", []),
            avoid_when=behavior_data.get("avoid_when", []),
            key_trigger=behavior_data.get("key_trigger", ""),
            triggers=behavior_data.get("triggers", []),
            on_init=behavior_data.get("on_init", ""),
            on_activate=behavior_data.get("on_activate", ""),
            on_deactivate=behavior_data.get("on_deactivate", ""),
        )

        # 解析限制
        limits_data = data.get("limits", {})
        limits = ExecutionLimits(
            is_readonly=limits_data.get("is_readonly", False),
            supports_background=limits_data.get("supports_background", True),
            max_concurrent=limits_data.get("max_concurrent", 3),
            timeout=limits_data.get("timeout", 300),
            max_iterations=limits_data.get("max_iterations", 50),
            max_subagent_depth=limits_data.get("max_subagent_depth", 3),
        )

        # 解析依赖
        dependencies_data = data.get("dependencies", {})
        dependencies = DependencyDefinition(
            requires=dependencies_data.get("requires", []),
            optional_requires=dependencies_data.get("optional_requires", []),
            conflicts_with=dependencies_data.get("conflicts_with", []),
        )

        # 解析记忆
        memory_data = data.get("memory", {})
        memory = MemoryConfiguration(
            enabled=memory_data.get("enabled", True),
            max_messages=memory_data.get("max_messages", 100),
            persistent_session=memory_data.get("persistent_session", False),
            compaction_threshold=memory_data.get("compaction_threshold", 80),
        )

        # 解析分类
        category_str = data.get("category", "coding")
        try:
            category = AgentCategory(category_str.lower())
        except ValueError:
            category = AgentCategory.CODING

        # 解析成本
        cost_str = data.get("cost", "moderate")
        try:
            cost = AgentCost(cost_str.lower())
        except ValueError:
            cost = AgentCost.MODERATE

        return AgentSchema(
            identity=identity,
            category=category,
            cost=cost,
            model=model,
            capabilities=capabilities,
            behavior=behavior,
            limits=limits,
            dependencies=dependencies,
            memory=memory,
            metadata=data.get("metadata", {}),
        )

    def _register_loaded(self, schema: AgentSchema, file_path: str) -> LoadedAgent:
        """
        注册已加载的 Agent

        Args:
            schema: Agent Schema
            file_path: 文件路径

        Returns:
            LoadedAgent 实例
        """
        name = schema.identity.name

        # 检查冲突
        has_conflicts, conflicts = self._dependency_resolver.check_conflicts(schema)
        if has_conflicts:
            raise AgentLoadError(
                f"Agent '{name}' conflicts with: {conflicts}", name
            )

        # 注册到 Registry
        metadata = schema.to_agent_metadata()
        self._registry.register(metadata)

        # 创建 LoadedAgent
        loaded = LoadedAgent(
            schema=schema,
            state=LoadState.LOADED,
            file_path=file_path,
        )

        self._loaded[name] = loaded

        logger.info(f"Loaded agent: {name} from {file_path}")
        return loaded
