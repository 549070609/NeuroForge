"""
PyAgentForge Plugin System

插件系统 - 提供可扩展的插件架构
"""

from pyagentforge.plugin.base import (
    Plugin,
    PluginContext,
    PluginMetadata,
    PluginType,
)
from pyagentforge.plugin.dependencies import (
    CircularDependencyError,
    DependencyMissingError,
    DependencyResolver,
)
from pyagentforge.plugin.hooks import HookRegistry, HookType
from pyagentforge.plugin.loader import PluginLoader, PluginLoadError
from pyagentforge.plugin.manager import PluginManager
from pyagentforge.plugin.registry import PluginRegistry, PluginState

__all__ = [
    # Base classes
    "Plugin",
    "PluginMetadata",
    "PluginContext",
    "PluginType",
    # Hooks
    "HookType",
    "HookRegistry",
    # Registry
    "PluginRegistry",
    "PluginState",
    # Dependencies
    "DependencyResolver",
    "CircularDependencyError",
    "DependencyMissingError",
    # Loader
    "PluginLoader",
    "PluginLoadError",
    # Manager
    "PluginManager",
]
