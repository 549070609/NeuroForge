"""
插件配置系统
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PluginConfig:
    """插件配置"""
    preset: str = "minimal"  # minimal, standard, full
    enabled: List[str] = field(default_factory=list)
    disabled: List[str] = field(default_factory=list)
    plugin_dirs: List[str] = field(default_factory=lambda: ["plugins"])
    config: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "PluginConfig":
        """从 YAML 文件加载配置"""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(
            preset=data.get("preset", "minimal"),
            enabled=data.get("enabled", []),
            disabled=data.get("disabled", []),
            plugin_dirs=data.get("plugin_dirs", ["plugins"]),
            config=data.get("config", {}),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginConfig":
        """从字典创建配置"""
        return cls(
            preset=data.get("preset", "minimal"),
            enabled=data.get("enabled", []),
            disabled=data.get("disabled", []),
            plugin_dirs=data.get("plugin_dirs", ["plugins"]),
            config=data.get("config", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "preset": self.preset,
            "enabled": self.enabled,
            "disabled": self.disabled,
            "plugin_dirs": self.plugin_dirs,
            "config": self.config,
        }

    def get_effective_plugins(self) -> List[str]:
        """获取最终启用的插件列表"""
        from pyagentforge.plugin.manager import PluginManager

        # 创建临时管理器获取预设
        manager = PluginManager()
        preset_plugins = manager._get_preset_plugins(self.preset)

        # 合并：预设 + enabled - disabled
        effective = (preset_plugins | set(self.enabled)) - set(self.disabled)
        return list(effective)

    def get_plugin_config(self, plugin_id: str) -> Dict[str, Any]:
        """获取特定插件的配置"""
        return self.config.get(plugin_id, {})


def load_preset(preset_name: str) -> PluginConfig:
    """加载预设配置"""
    presets = {
        "minimal": PluginConfig(preset="minimal"),
        "standard": PluginConfig(
            preset="standard",
            enabled=[],
            plugin_dirs=["plugins"],
        ),
        "full": PluginConfig(
            preset="full",
            enabled=[],
            plugin_dirs=["plugins"],
        ),
    }
    return presets.get(preset_name, PluginConfig())
