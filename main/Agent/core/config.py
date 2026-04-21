"""
Agent 底座配置

提供 Agent 底座系统的配置管理。

目录结构:
main/Agent/
├── core/                 # 核心模块 (配置、目录扫描)
├── mate-agent/           # 元级 Agent + 共享工具/模板
│   ├── agent.yaml
│   ├── system_prompt.md
│   ├── tools/            # MateAgent 专用工具 (被所有 Agent 共享)
│   ├── templates/        # Agent 模板
│   ├── subagents/        # 子Agent
│   └── docs/             # 文档
├── {agent-id}/           # 其他 Agent
│   ├── agent.yaml
│   └── system_prompt.md
└── config.yaml           # 配置文件
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


# 需要排除的目录（不是 Agent 目录，或 Agent 目录中的非配置子目录）
EXCLUDED_DIRS = {
    "core",
    "__pycache__",
    ".git",
    ".backups",
}


class AgentBaseConfig(BaseModel):
    """
    Agent 底座配置

    Attributes:
        base_path: Agent 根目录路径
        mate_agent_dir: MateAgent 目录名 (包含共享工具和模板)
        default_namespace: 默认命名空间
    """

    base_path: str = Field(default="main/Agent", description="Agent 根目录路径")
    mate_agent_dir: str = Field(default="mate-agent", description="MateAgent 目录名")
    default_namespace: str = Field(default="default", description="默认命名空间")

    # Agent 加载配置
    auto_load: bool = Field(default=True, description="是否自动加载 Agent")
    hot_reload: bool = Field(default=False, description="是否启用热重载")

    # 执行配置
    max_concurrent_per_agent: int = Field(default=3, description="每个 Agent 最大并发数")
    default_timeout: int = Field(default=300, description="默认超时时间 (秒)")

    # 排除目录
    excluded_dirs: set[str] = Field(
        default_factory=lambda: EXCLUDED_DIRS,
        description="扫描时排除的目录"
    )

    model_config = ConfigDict(extra="forbid")

    def get_full_path(self) -> Path:
        """获取完整的基础路径"""
        return Path(self.base_path)

    def get_mate_agent_path(self) -> Path:
        """获取 MateAgent 目录路径"""
        return self.get_full_path() / self.mate_agent_dir

    def get_tools_path(self) -> Path:
        """获取共享工具目录路径 (在 mate-agent 下)"""
        return self.get_mate_agent_path() / "tools"

    def get_templates_path(self) -> Path:
        """获取模板目录路径 (在 mate-agent 下)"""
        return self.get_mate_agent_path() / "templates"

    def is_excluded(self, dir_name: str) -> bool:
        """
        检查目录是否应被排除

        Args:
            dir_name: 目录名

        Returns:
            是否排除
        """
        return dir_name in self.excluded_dirs or dir_name.startswith(".")

    @classmethod
    def from_yaml(cls, path: str) -> "AgentBaseConfig":
        """
        从 YAML 文件加载配置

        Args:
            path: YAML 文件路径

        Returns:
            AgentBaseConfig 实例
        """
        file_path = Path(path)
        if not file_path.exists():
            return cls()

        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    def to_yaml(self, path: str) -> None:
        """
        保存配置到 YAML 文件

        Args:
            path: YAML 文件路径
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 排除 excluded_dirs（使用默认值）
        output_data = self.model_dump(exclude={"excluded_dirs"})
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(output_data, f, default_flow_style=False, allow_unicode=True)


# 全局配置实例
_config: AgentBaseConfig | None = None


def get_agent_base_config() -> AgentBaseConfig:
    """
    获取全局 Agent 底座配置实例

    Returns:
        AgentBaseConfig 单例实例
    """
    global _config
    if _config is None:
        # 尝试从配置文件加载
        config_path = Path("main/Agent/config.yaml")
        if config_path.exists():
            _config = AgentBaseConfig.from_yaml(str(config_path))
        else:
            _config = AgentBaseConfig()
    return _config


def set_agent_base_config(config: AgentBaseConfig) -> None:
    """
    设置全局 Agent 底座配置

    Args:
        config: AgentBaseConfig 实例
    """
    global _config
    _config = config
