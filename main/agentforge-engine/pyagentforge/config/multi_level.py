"""
多级配置系统

支持用户级和项目级配置文件的合并。

配置层级（优先级从低到高）:
1. 代码默认值
2. 用户级配置: ~/.config/pyagentforge/config.yaml
3. 项目级配置: ./pyagentforge.yaml
4. 环境变量: .env (最高优先级)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError
import yaml

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ConfigSource:
    """配置来源信息"""

    name: str
    path: Path
    exists: bool = False
    loaded: bool = False
    error: str | None = None


@dataclass
class ConfigLayer:
    """配置层级"""

    source: ConfigSource
    data: dict[str, Any] = field(default_factory=dict)


class MultiLevelConfig:
    """
    多级配置管理器

    负责加载、合并和验证多级配置。

    Usage:
        config = MultiLevelConfig()
        merged = config.load_merged()
        # merged 包含合并后的配置字典
    """

    def __init__(
        self,
        user_config_dir: Path | None = None,
        project_config_path: Path | None = None,
        env_file_path: Path | None = None,
    ):
        """
        初始化多级配置管理器

        Args:
            user_config_dir: 用户配置目录（默认 ~/.config/pyagentforge/）
            project_config_path: 项目配置文件路径（默认 ./pyagentforge.yaml）
            env_file_path: 环境变量文件路径（默认 ./.env）
        """
        # 确定配置路径
        self.user_config_path = (
            user_config_dir or Path.home() / ".config" / "pyagentforge"
        ) / "config.yaml"

        self.project_config_path = project_config_path or Path.cwd() / "pyagentforge.yaml"

        self.env_file_path = env_file_path or Path.cwd() / ".env"

        # 配置来源
        self.sources: list[ConfigSource] = [
            ConfigSource("user", self.user_config_path),
            ConfigSource("project", self.project_config_path),
            ConfigSource("env", self.env_file_path),
        ]

    def load_merged(self) -> dict[str, Any]:
        """
        加载并合并所有配置层

        Returns:
            合并后的配置字典
        """
        layers: list[ConfigLayer] = []

        # 加载用户配置
        user_layer = self._load_yaml_layer(self.sources[0])
        if user_layer.data:
            layers.append(user_layer)

        # 加载项目配置
        project_layer = self._load_yaml_layer(self.sources[1])
        if project_layer.data:
            layers.append(project_layer)

        # 加载环境变量配置
        env_layer = self._load_env_layer(self.sources[2])
        if env_layer.data:
            layers.append(env_layer)

        # 合并配置
        merged = self._merge_layers(layers)

        logger.info(
            "Configuration loaded",
            extra_data={
                "layers": len(layers),
                "sources": [layer.source.name for layer in layers],
            },
        )

        return merged

    def _load_yaml_layer(self, source: ConfigSource) -> ConfigLayer:
        """
        加载 YAML 配置层

        Args:
            source: 配置来源

        Returns:
            配置层
        """
        source.exists = source.path.exists()

        if not source.exists:
            return ConfigLayer(source=source, data={})

        try:
            content = source.path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
            source.loaded = True

            logger.debug(
                f"Loaded {source.name} config",
                extra_data={
                    "path": str(source.path),
                    "keys": list(data.keys()),
                },
            )

            return ConfigLayer(source=source, data=data)

        except yaml.YAMLError as e:
            source.error = str(e)
            logger.warning(
                f"Failed to parse {source.name} config: {e}",
                extra_data={"path": str(source.path)},
            )
            return ConfigLayer(source=source, data={})

        except Exception as e:
            source.error = str(e)
            logger.warning(
                f"Failed to load {source.name} config: {e}",
                extra_data={"path": str(source.path)},
            )
            return ConfigLayer(source=source, data={})

    def _load_env_layer(self, source: ConfigSource) -> ConfigLayer:
        """
        加载 .env 文件配置层

        .env 文件使用 KEY=VALUE 格式，会被转换为嵌套字典。

        Args:
            source: 配置来源

        Returns:
            配置层
        """
        source.exists = source.path.exists()

        if not source.exists:
            return ConfigLayer(source=source, data={})

        try:
            data: dict[str, Any] = {}

            content = source.path.read_text(encoding="utf-8")

            for line in content.splitlines():
                line = line.strip()

                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue

                # 解析 KEY=VALUE
                if "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip().lower()  # 转换为小写
                value = value.strip()

                # 移除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # 转换为嵌套结构（用 _ 分隔）
                self._set_nested(data, key.split("_"), value)

            source.loaded = True

            return ConfigLayer(source=source, data=data)

        except Exception as e:
            source.error = str(e)
            logger.warning(
                f"Failed to load {source.name} config: {e}",
                extra_data={"path": str(source.path)},
            )
            return ConfigLayer(source=source, data={})

    def _set_nested(
        self,
        data: dict[str, Any],
        keys: list[str],
        value: Any,
    ) -> None:
        """
        设置嵌套字典值

        Args:
            data: 目标字典
            keys: 键路径
            value: 值
        """
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]

        # 尝试类型转换
        final_key = keys[-1]
        data[final_key] = self._convert_value(value)

    def _convert_value(self, value: str) -> Any:
        """
        转换字符串值为适当的类型

        Args:
            value: 字符串值

        Returns:
            转换后的值
        """
        # 布尔值
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # None
        if value.lower() in ("none", "null", ""):
            return None

        # 整数
        try:
            return int(value)
        except ValueError:
            pass

        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass

        # 保持字符串
        return value

    def _merge_layers(self, layers: list[ConfigLayer]) -> dict[str, Any]:
        """
        合并配置层

        后面的层覆盖前面的层。

        Args:
            layers: 配置层列表

        Returns:
            合并后的配置
        """
        merged: dict[str, Any] = {}

        for layer in layers:
            merged = self._deep_merge(merged, layer.data)

        return merged

    def _deep_merge(
        self,
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """
        深度合并两个字典

        Args:
            base: 基础字典
            override: 覆盖字典

        Returns:
            合并后的字典
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def get_config_status(self) -> list[dict[str, Any]]:
        """
        获取配置来源状态

        Returns:
            配置来源状态列表
        """
        return [
            {
                "name": source.name,
                "path": str(source.path),
                "exists": source.exists,
                "loaded": source.loaded,
                "error": source.error,
            }
            for source in self.sources
        ]

    def generate_user_config_template(self) -> str:
        """
        生成用户配置模板

        Returns:
            YAML 格式的配置模板
        """
        template = """# PyAgentForge User Configuration
# This file is located at ~/.config/pyagentforge/config.yaml
# Project-level configuration in ./pyagentforge.yaml will override this

# LLM Configuration
llm:
  default_model: "default"
  max_tokens: 4096
  temperature: 1.0

# Agent Configuration
agent:
  default_timeout: 120
  tool_timeout: 60
  max_subagent_depth: 3
  max_context_messages: 100

# Context Compaction
compaction:
  enabled: true
  threshold: 0.8
  reserve_tokens: 8000
  keep_recent_tokens: 4000

# Logging
log:
  level: "INFO"
  format: "json"

# Session Recovery
session_recovery:
  enabled: true
  auto_save: true
  auto_save_interval: 5
"""
        return template

    def generate_project_config_template(self) -> str:
        """
        生成项目配置模板

        Returns:
            YAML 格式的配置模板
        """
        template = """# PyAgentForge Project Configuration
# This file overrides user-level configuration

# Project-specific model
llm:
  default_model: "default"

# Project-specific agent settings
agent:
  max_context_messages: 200

# Enable session recovery for this project
session_recovery:
  enabled: true
"""
        return template

    def create_user_config(self) -> bool:
        """
        创建用户配置文件

        Returns:
            是否成功创建
        """
        try:
            # 确保目录存在
            self.user_config_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入模板
            template = self.generate_user_config_template()
            self.user_config_path.write_text(template, encoding="utf-8")

            logger.info(
                "Created user config template",
                extra_data={"path": str(self.user_config_path)},
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to create user config: {e}",
                extra_data={"path": str(self.user_config_path)},
            )
            return False

    def create_project_config(self) -> bool:
        """
        创建项目配置文件

        Returns:
            是否成功创建
        """
        try:
            if self.project_config_path.exists():
                logger.warning(
                    "Project config already exists",
                    extra_data={"path": str(self.project_config_path)},
                )
                return False

            template = self.generate_project_config_template()
            self.project_config_path.write_text(template, encoding="utf-8")

            logger.info(
                "Created project config template",
                extra_data={"path": str(self.project_config_path)},
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to create project config: {e}",
                extra_data={"path": str(self.project_config_path)},
            )
            return False


def load_multi_level_settings(
    settings_class: type | None = None,
) -> dict[str, Any]:
    """
    便捷函数：加载多级配置

    Args:
        settings_class: 可选的 Settings 类（用于验证）

    Returns:
        合并后的配置字典
    """
    config = MultiLevelConfig()
    return config.load_merged()
