"""
Agent Directory - Agent 目录扫描器

扫描和管理 Agent 目录:

目录结构:
main/Agent/
├── {agent-id}/           # Agent 目录 (直接在根目录下)
│   ├── agent.yaml
│   └── system_prompt.md
├── core/                 # 核心模块 (排除)
├── tools/                # 工具 (排除)
├── templates/            # 模板 (排除)
└── config.yaml           # 配置文件
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .config import AgentBaseConfig, get_agent_base_config

logger = logging.getLogger(__name__)


class AgentOrigin(str, Enum):
    """Agent 来源类型"""

    LOCAL = "local"  # 本地 Agent (直接在根目录下)
    BUNDLED = "bundled"  # pyagentforge 内置 Agent
    CONFIG = "config"  # 运行时配置覆盖


@dataclass
class AgentInfo:
    """
    Agent 信息

    存储扫描到的 Agent 基本信息和元数据
    """

    name: str  # Agent 名称
    origin: AgentOrigin  # 来源类型
    namespace: str  # 命名空间 (默认为 'default')
    agent_id: str  # 完整 Agent ID (= name)
    file_path: Path  # Agent 定义文件路径
    system_prompt_path: Path | None = None  # 系统提示词文件路径
    description: str = ""  # 描述
    tags: list[str] = field(default_factory=list)  # 标签
    category: str = "coding"  # 类别
    priority: int = 0  # 优先级 (数字越大优先级越高)
    metadata: dict[str, Any] = field(default_factory=dict)  # 扩展元数据

    @property
    def is_local(self) -> bool:
        """是否为本地 Agent"""
        return self.origin == AgentOrigin.LOCAL


class AgentDirectory:
    """
    Agent 目录扫描器

    扫描 main/Agent/ 目录下的所有子目录，每个子目录代表一个 Agent。

    排除目录: core, tools, templates, plans, namespaces, public, __pycache__, .git, .backups

    优先级 (高到低):
    1. config - 运行时配置覆盖
    2. local - 本地 Agent
    3. bundled - pyagentforge 内置 Agent
    """

    def __init__(self, config: AgentBaseConfig | None = None):
        """
        初始化目录扫描器

        Args:
            config: Agent 底座配置 (可选，默认使用全局配置)
        """
        self._config = config or get_agent_base_config()
        self._agents: dict[str, AgentInfo] = {}
        self._initialized = False

    # ==================== 扫描方法 ====================

    def scan(self) -> dict[str, AgentInfo]:
        """
        扫描所有 Agent 目录

        Returns:
            Agent ID -> AgentInfo 映射
        """
        self._agents.clear()

        # 扫描根目录下的所有 Agent
        self._scan_local_agents()

        self._initialized = True
        logger.info(
            f"Agent directory scan complete: {len(self._agents)} agents"
        )

        return self._agents

    def _scan_local_agents(self) -> None:
        """扫描根目录下的 Agent"""
        base_path = self._config.get_full_path()
        if not base_path.exists():
            logger.debug(f"Base directory does not exist: {base_path}")
            return

        for item in base_path.iterdir():
            # 只处理目录
            if not item.is_dir():
                continue

            # 跳过排除的目录
            if self._config.is_excluded(item.name):
                logger.debug(f"Excluded directory: {item.name}")
                continue

            agent_info = self._load_agent_info(
                agent_dir=item,
                origin=AgentOrigin.LOCAL,
            )

            if agent_info:
                self._agents[agent_info.agent_id] = agent_info
                logger.debug(f"Found local agent: {agent_info.agent_id}")

    def _load_agent_info(
        self,
        agent_dir: Path,
        origin: AgentOrigin,
    ) -> AgentInfo | None:
        """
        加载 Agent 信息

        Args:
            agent_dir: Agent 目录路径
            origin: 来源类型

        Returns:
            AgentInfo 或 None
        """
        # 查找 Agent 定义文件
        agent_file = None
        for ext in [".yaml", ".yml", ".json"]:
            candidate = agent_dir / f"agent{ext}"
            if candidate.exists():
                agent_file = candidate
                break

        if agent_file is None:
            logger.debug(f"No agent definition file found in: {agent_dir}")
            return None

        # 加载定义文件
        try:
            with open(agent_file, encoding="utf-8") as f:
                if agent_file.suffix == ".json":
                    import json
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load agent file {agent_file}: {e}")
            return None

        # 提取信息
        identity = data.get("identity", {})
        name = identity.get("name", agent_dir.name)

        # Agent ID = name（简化逻辑）
        agent_id = name

        # 检查系统提示词文件
        system_prompt_path = agent_dir / "system_prompt.md"
        if not system_prompt_path.exists():
            system_prompt_path = None

        # 计算优先级
        priority = self._calculate_priority(origin)

        return AgentInfo(
            name=name,
            origin=origin,
            namespace=self._config.default_namespace,
            agent_id=agent_id,
            file_path=agent_file,
            system_prompt_path=system_prompt_path,
            description=identity.get("description", ""),
            tags=identity.get("tags", []),
            category=data.get("category", "coding"),
            priority=priority,
            metadata=data,
        )

    def _calculate_priority(self, origin: AgentOrigin) -> int:
        """
        计算优先级

        优先级: config > local > bundled

        Args:
            origin: 来源类型

        Returns:
            优先级数字 (越大越高)
        """
        priority_map = {
            AgentOrigin.CONFIG: 40,
            AgentOrigin.LOCAL: 20,
            AgentOrigin.BUNDLED: 10,
        }
        return priority_map.get(origin, 0)

    # ==================== 查询方法 ====================

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """
        获取 Agent 信息

        Args:
            agent_id: Agent ID

        Returns:
            AgentInfo 或 None
        """
        if not self._initialized:
            self.scan()
        return self._agents.get(agent_id)

    def list_agents(
        self,
        namespace: str | None = None,
        origin: AgentOrigin | None = None,
        tags: list[str] | None = None,
    ) -> list[AgentInfo]:
        """
        列出 Agent

        Args:
            namespace: 过滤命名空间 (可选)
            origin: 过滤来源类型 (可选)
            tags: 过滤标签 (可选，满足任一即可)

        Returns:
            AgentInfo 列表
        """
        if not self._initialized:
            self.scan()

        agents = list(self._agents.values())

        # 过滤来源
        if origin:
            agents = [a for a in agents if a.origin == origin]

        # 过滤标签
        if tags:
            agents = [a for a in agents if any(t in a.tags for t in tags)]

        # 按优先级排序
        agents.sort(key=lambda a: a.priority, reverse=True)

        return agents

    def resolve_agent_id(self, name: str) -> str | None:
        """
        解析 Agent ID

        Args:
            name: Agent 名称

        Returns:
            Agent ID 或 None
        """
        if not self._initialized:
            self.scan()

        # 直接按名称查找
        if name in self._agents:
            return name

        return None

    # ==================== 缓存管理 ====================

    def refresh(self) -> None:
        """刷新缓存，重新扫描目录"""
        self.scan()

    def clear(self) -> None:
        """清空缓存"""
        self._agents.clear()
        self._initialized = False

    # ==================== 统计信息 ====================

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计字典
        """
        if not self._initialized:
            self.scan()

        origin_counts = {}
        for origin in AgentOrigin:
            count = sum(1 for a in self._agents.values() if a.origin == origin)
            if count > 0:
                origin_counts[origin.value] = count

        return {
            "total_agents": len(self._agents),
            "by_origin": origin_counts,
        }
